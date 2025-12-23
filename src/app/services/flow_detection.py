"""
Flow 检测流水线。

职责：
- 从控制层 WebSocket 事件中接收 FLOW_UPDATE 事件
- 将 Flow 以旁路方式写入应用层数据库 app_flows
- 将 Flow 加入本地检测队列
- 后台 worker 批量调用推理服务进行检测，并更新 app_flows 状态
- 通过 UI WebSocket 向前端推送 flow_detection_update 事件
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .event_subscriber import Event, EventType
from .inference import DecisionLevel, get_inference_service
from ..db import session_scope
from ..db.models import AppFlow
from .ui_events_ws import enqueue_ui_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 配置参数（后续可接入 app.config 覆盖）
# ---------------------------------------------------------------------------

QUEUE_MAX_SIZE = 10_000
BATCH_SIZE = 64
WORKER_COUNT = 1


@dataclass
class FlowTask:
    flow_id: str
    flow: Dict[str, Any]


_task_queue: "queue.Queue[FlowTask]" = queue.Queue(maxsize=QUEUE_MAX_SIZE)
_workers_started = False
_worker_threads: List[threading.Thread] = []


def _parse_iso8601(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # datetime.fromisoformat 支持带时区的 ISO8601 字符串
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def handle_flow_event(event: Event) -> None:
    """
    处理来自控制层的 FLOW_UPDATE 事件：
    - 将 Flow 写入 app_flows（detect_status=pending）
    - 将 Flow 加入检测队列
    """
    if event.event_type != EventType.FLOW_UPDATE:
        return

    data = event.data or {}
    # 兼容两种结构：
    # 1) data: { id/src_ip/... }
    # 2) data: { flow: { id/src_ip/... } }（见 docs/api/README.md 中 flow_update 说明）
    flow = data.get("flow") or data

    # 必须使用控制层提供的 flow_id/id；缺失则放弃处理，避免生成错误 ID
    flow_id_raw = flow.get("flow_id") or flow.get("id")
    if not flow_id_raw:
        logger.warning("FLOW_UPDATE missing flow_id/id, skip detection enqueue: raw=%s", data)
        return
    flow_id = str(flow_id_raw)

    src_ip = flow.get("src_ip")
    dst_ip = flow.get("dst_ip")
    src_port = flow.get("src_port")
    dst_port = flow.get("dst_port")
    protocol = flow.get("protocol")

    start_time = _parse_iso8601(flow.get("start_time"))
    end_time = _parse_iso8601(flow.get("end_time"))

    duration = flow.get("duration")
    pkt_count = flow.get("pkt_count")
    byte_count = flow.get("byte_count")
    pkt_rate = flow.get("pkt_rate")
    byte_rate = flow.get("byte_rate")
    func_code_entropy = flow.get("func_code_entropy")
    reg_addr_std = flow.get("reg_addr_std")

    # 将 Flow 写入 app_flows（若已存在则跳过插入，只更新基础字段）
    try:
        with session_scope() as session:
            existing: Optional[AppFlow] = session.query(AppFlow).filter_by(flow_id=flow_id).first()
            if existing is None:
                flow_row = AppFlow(
                    flow_id=flow_id,
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    src_port=src_port,
                    dst_port=dst_port,
                    protocol=protocol,
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    pkt_count=pkt_count,
                    byte_count=byte_count,
                    pkt_rate=pkt_rate,
                    byte_rate=byte_rate,
                    func_code_entropy=func_code_entropy,
                    reg_addr_std=reg_addr_std,
                    detect_status="pending",
                    decision_level="normal",
                    prob=0.0,
                    anomaly_score=0.0,
                    raw_snapshot=None,
                )
                session.add(flow_row)
            else:
                # 更新基础字段，但不覆盖检测结果
                existing.src_ip = src_ip
                existing.dst_ip = dst_ip
                existing.src_port = src_port
                existing.dst_port = dst_port
                existing.protocol = protocol
                existing.start_time = start_time
                existing.end_time = end_time
                existing.duration = duration
                existing.pkt_count = pkt_count
                existing.byte_count = byte_count
                existing.pkt_rate = pkt_rate
                existing.byte_rate = byte_rate
                existing.func_code_entropy = func_code_entropy
                existing.reg_addr_std = reg_addr_std
    except Exception as e:
        logger.error("Failed to persist flow to app_flows: %s", e, exc_info=True)
        # 即便写库失败，也不要影响后续 UI 显示或收流

    # 将 Flow 加入检测队列
    task = FlowTask(flow_id=flow_id, flow=flow)
    try:
        _task_queue.put_nowait(task)
    except queue.Full:
        # 队列已满，标记为 skipped
        logger.warning("Flow detection queue is full, skipping flow_id=%s", flow_id)
        try:
            with session_scope() as session:
                row: Optional[AppFlow] = session.query(AppFlow).filter_by(flow_id=flow_id).first()
                if row is not None:
                    row.detect_status = "skipped"
        except Exception:
            # 不能因为标记失败影响主流程
            pass


def _map_decision_to_status(level: DecisionLevel) -> str:
    if level == DecisionLevel.NORMAL:
        return "safe"
    if level == DecisionLevel.ALERT:
        return "suspicious"
    if level in (DecisionLevel.THROTTLE, DecisionLevel.BLOCK, DecisionLevel.REDIRECT):
        return "dangerous"
    return "error"


def _worker_loop() -> None:
    """
    检测 worker 主循环：
    - 从队列批量取 FlowTask
    - 调用 InferenceService.predict_batch
    - 批量更新 app_flows
    - 为每条 flow 推送 flow_detection_update 事件
    """
    service = get_inference_service()

    while True:
        tasks: List[FlowTask] = []
        try:
            # 阻塞获取一条，保证即使队列短暂为空也能继续工作
            first = _task_queue.get()
            tasks.append(first)
        except Exception:
            continue

        # 尝试再取最多 BATCH_SIZE-1 条，使用非阻塞方式
        try:
            while len(tasks) < BATCH_SIZE:
                next_task = _task_queue.get_nowait()
                tasks.append(next_task)
        except queue.Empty:
            pass

        flows = [t.flow for t in tasks]

        # 执行批量推理
        try:
            results = service.predict_batch(flows)
        except Exception as e:
            logger.error("Flow batch prediction failed: %s", e, exc_info=True)
            # 全部标记为 error
            _update_flows_detection(tasks, None, error=e)
            continue

        _update_flows_detection(tasks, results, error=None)


def _update_flows_detection(
    tasks: List[FlowTask],
    results: Optional[List[Any]],
    error: Optional[BaseException],
) -> None:
    """
    根据推理结果更新 app_flows，并通过 UI WS 推送状态更新事件。
    """
    now = datetime.now(timezone.utc).isoformat()

    try:
        with session_scope() as session:
            for idx, task in enumerate(tasks):
                flow_id = task.flow_id
                row: Optional[AppFlow] = session.query(AppFlow).filter_by(flow_id=flow_id).first()
                if row is None:
                    continue

                if error is not None or results is None or idx >= len(results):
                    row.detect_status = "error"
                    row.decision_level = "normal"
                    row.prob = 0.0
                    row.anomaly_score = 0.0
                    row.detected_at = datetime.now(timezone.utc)
                    status = "error"
                    prob = 0.0
                    decision_level = "normal"
                else:
                    r = results[idx]
                    status = _map_decision_to_status(r.decision_level)
                    prob = float(r.prob)
                    decision_level = r.decision_level.value

                    row.detect_status = status
                    row.decision_level = decision_level
                    row.prob = prob
                    row.anomaly_score = float(r.anomaly_score)
                    row.detected_at = datetime.now(timezone.utc)

                # 推送 UI 事件
                try:
                    enqueue_ui_event(
                        {
                            "type": "flow_detection_update",
                            "timestamp": now,
                            "data": {
                                "flow_id": flow_id,
                                "detect_status": status,
                                "prob": prob,
                                "decision_level": decision_level,
                            },
                        }
                    )
                except Exception as e:
                    logger.debug("enqueue_ui_event(flow_detection_update) failed: %s", e)
    except Exception as e:
        logger.error("Failed to update flow detection results: %s", e, exc_info=True)


def start_flow_detection_workers() -> None:
    """
    启动 Flow 检测 worker（幂等，多次调用只会启动一次）。
    """
    global _workers_started
    if _workers_started:
        return

    _workers_started = True
    for i in range(WORKER_COUNT):
        t = threading.Thread(target=_worker_loop, name=f"flow-detect-worker-{i}", daemon=True)
        t.start()
        _worker_threads.append(t)
        logger.info("Flow detection worker %d started", i)


