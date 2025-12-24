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

import json
import logging
import queue
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .event_subscriber import Event, EventType, record_event_for_ui
from .inference import DecisionLevel, get_inference_service
from ..db import session_scope
from ..db.models import AppFlow, FlowDetectionLog
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

    import json

    # 新增字段（根据新版API文档）
    policy_effects = flow.get("policy_effects")
    redirect_to = flow.get("redirect_to")
    final_dst = flow.get("final_dst")
    blocked = flow.get("blocked")
    blocked_at = _parse_iso8601(flow.get("blocked_at"))
    block_reason = flow.get("block_reason")
    path_hops = flow.get("path_hops")

    # 序列化复杂对象为JSON字符串（适用于数据库存储）
    policy_effects_json = json.dumps(policy_effects) if policy_effects is not None else None
    redirect_to_json = json.dumps(redirect_to) if redirect_to is not None else None
    final_dst_json = json.dumps(final_dst) if final_dst is not None else None
    path_hops_json = json.dumps(path_hops) if path_hops is not None else None

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
                    # 新增字段（JSON序列化）
                    policy_effects=policy_effects_json,
                    redirect_to=redirect_to_json,
                    final_dst=final_dst_json,
                    blocked=blocked,
                    blocked_at=blocked_at,
                    block_reason=block_reason,
                    path_hops=path_hops_json,
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
                # 更新新增字段（JSON序列化）
                existing.policy_effects = policy_effects_json
                existing.redirect_to = redirect_to_json
                existing.final_dst = final_dst_json
                existing.blocked = blocked
                existing.blocked_at = blocked_at
                existing.block_reason = block_reason
                existing.path_hops = path_hops_json
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
    同时记录检测历史到 FlowDetectionLog。
    """
    now = datetime.now(timezone.utc).isoformat()

    try:
        with session_scope() as session:
            for idx, task in enumerate(tasks):
                flow_id = task.flow_id
                row: Optional[AppFlow] = session.query(AppFlow).filter_by(flow_id=flow_id).first()
                if row is None:
                    continue

                label = "Unknown"
                if error is not None or results is None or idx >= len(results):
                    row.detect_status = "error"
                    row.decision_level = "normal"
                    row.prob = 0.0
                    row.anomaly_score = 0.0
                    row.detected_at = datetime.now(timezone.utc)
                    status = "error"
                    prob = 0.0
                    decision_level = "normal"
                    label = "Error"
                else:
                    r = results[idx]
                    status = _map_decision_to_status(r.decision_level)
                    prob = float(r.prob)
                    decision_level = r.decision_level.value
                    label = r.label

                    row.detect_status = status
                    row.decision_level = decision_level
                    row.prob = prob
                    row.anomaly_score = float(r.anomaly_score)
                    row.detected_at = datetime.now(timezone.utc)

                # 记录检测历史
                try:
                    det_log = FlowDetectionLog(
                        flow_id=flow_id,
                        prob=prob,
                        label=label,
                        anomaly_score=row.anomaly_score,
                        decision_level=decision_level,
                        payload_snapshot=json.dumps(task.flow, ensure_ascii=False)
                    )
                    session.add(det_log)
                except Exception as e:
                    logger.error("Failed to record flow detection log: %s", e)

                # 推送 UI 事件
                try:
                    # 1. 实时推送 (WebSocket)
                    # 仅当状态为 dangerous/suspicious 或概率较高时才推送，避免刷屏
                    # 或者当状态发生变化时推送（需要缓存上一次状态，这里简化为只推异常）
                    should_push = False
                    if status in ("dangerous", "suspicious"):
                        should_push = True
                    elif prob > 0.1: # 稍微放宽一点，关注度高的才推
                        should_push = True
                    
                    # 如果是第一次检测（没有历史记录），也可以推一下，但这里无法判断是否第一次
                    # 暂时只推异常，减少刷屏
                    
                    if should_push:
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
                        
                        # 2. 记录到自动化事件日志 (EventLog)
                        # 构造一个内部事件并记录
                        det_event = Event(
                            event_type=EventType.FLOW_DETECTION,
                            timestamp=now,
                            data={
                                "flow_id": flow_id,
                                "detect_status": status,
                                "label": label,
                                "prob": prob,
                                "decision_level": decision_level,
                            }
                        )
                        record_event_for_ui(det_event)
                except Exception as e:
                    logger.debug("Failed to push/record flow detection event: %s", e)
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


