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
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .event_subscriber import Event, EventType, record_event_for_ui
from .inference import DecisionLevel, get_inference_service
from .controller_client import get_controller_client
from ..db import session_scope
from ..db.models import AppFlow, FlowDetectionLog
from .ui_events_ws import enqueue_ui_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 配置参数（后续可接入 app.config 覆盖）
# ---------------------------------------------------------------------------

QUEUE_MAX_SIZE = 10_000
BATCH_SIZE = 64
WORKER_COUNT = 4  # 使用线程池，默认 4 个工作线程


@dataclass
class FlowTask:
    flow_id: str
    flow: Dict[str, Any]


_task_queue: "queue.Queue[FlowTask]" = queue.Queue(maxsize=QUEUE_MAX_SIZE)
_db_lock = threading.Lock()
_workers_started = False
_executor: Optional[ThreadPoolExecutor] = None
_batcher_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()

# 用于追踪已自动响应的流，避免重复创建策略
_responded_flows: Set[str] = set()
_responded_flows_lock = threading.Lock()


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
    - 将 Flow 加入检测队列（异步处理写库和检测）
    """
    if event.event_type != EventType.FLOW_UPDATE:
        return

    data = event.data or {}
    flow = data.get("flow") or data

    # 必须使用控制层提供的 flow_id/id；缺失则放弃处理
    flow_id_raw = flow.get("flow_id") or flow.get("id")
    if not flow_id_raw:
        logger.warning("FLOW_UPDATE missing flow_id/id, skip detection enqueue: raw=%s", data)
        return
    flow_id = str(flow_id_raw)

    # [DEBUG] 记录接收到的高频流
    pkt_rate = flow.get("pkt_rate")
    # print(f"DEBUG: Check flow {flow_id} rate={pkt_rate}") # 强制打印所有流速率
    if pkt_rate and float(pkt_rate) > 1000:
        msg = f"Received HIGH RATE flow event: id={flow_id} rate={pkt_rate}"
        logger.info(msg)
        print(f"!!! {msg} !!!") # 强制输出到控制台

    # 检查是否被阻断或重定向，并记录自动化日志
    try:
        is_blocked = flow.get("blocked", False)
        redirect_to = flow.get("redirect_to")
        
        if is_blocked or redirect_to:
            # 使用 _responded_flows 集合来避免对同一个流重复记录自动化日志
            # 虽然这个集合原本是用于自动响应的，但也可以借用来做日志去重
            with _responded_flows_lock:
                log_key = f"log_{flow_id}_{'block' if is_blocked else 'redirect'}"
                if log_key not in _responded_flows:
                    _responded_flows.add(log_key)
                    
                    event_type = EventType.TRAFFIC_BLOCK if is_blocked else EventType.TRAFFIC_REDIRECT
                    now = datetime.now(timezone.utc).isoformat()
                    
                    log_event = Event(
                        event_type=event_type,
                        timestamp=now,
                        data={
                            "flow_id": flow_id,
                            "src_ip": flow.get("src_ip"),
                            "dst_ip": flow.get("dst_ip"),
                            "redirect_to": redirect_to,
                            "block_reason": flow.get("block_reason"),
                            "flow_details": flow
                        }
                    )
                    record_event_for_ui(log_event)
                    logger.info("Recorded automation log for %s flow: %s", "blocked" if is_blocked else "redirected", flow_id)
    except Exception as e:
        logger.error("Failed to record automation log for flow event: %s", e)

    # 将 Flow 加入检测队列
    task = FlowTask(flow_id=flow_id, flow=flow)
    try:
        _task_queue.put_nowait(task)
    except queue.Full:
        logger.warning("Flow detection queue is full, skipping flow_id=%s", flow_id)
        # 尝试标记为 skipped（可选，此处为了性能暂不操作 DB）


def _map_decision_to_status(level: DecisionLevel) -> str:
    if level == DecisionLevel.NORMAL:
        return "safe"
    if level == DecisionLevel.ALERT:
        return "suspicious"
    if level in (DecisionLevel.THROTTLE, DecisionLevel.BLOCK, DecisionLevel.REDIRECT):
        return "dangerous"
    return "error"


def _sync_flow_to_db(session: Any, task: FlowTask) -> Optional[AppFlow]:
    """将 Flow 基础信息同步到数据库。"""
    flow = task.flow
    flow_id = task.flow_id

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

    # 新增字段
    policy_effects = flow.get("policy_effects")
    redirect_to = flow.get("redirect_to")
    final_dst = flow.get("final_dst")
    blocked = flow.get("blocked")
    blocked_at = _parse_iso8601(flow.get("blocked_at"))
    block_reason = flow.get("block_reason")
    path_hops = flow.get("path_hops")

    policy_effects_json = json.dumps(policy_effects) if policy_effects is not None else None
    redirect_to_json = json.dumps(redirect_to) if redirect_to is not None else None
    final_dst_json = json.dumps(final_dst) if final_dst is not None else None
    path_hops_json = json.dumps(path_hops) if path_hops is not None else None

    # 尝试获取现有记录
    existing: Optional[AppFlow] = session.query(AppFlow).filter_by(flow_id=flow_id).first()
    
    if existing:
        # 更新现有记录
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
        existing.policy_effects = policy_effects_json
        existing.redirect_to = redirect_to_json
        existing.final_dst = final_dst_json
        existing.blocked = blocked
        existing.blocked_at = blocked_at
        existing.block_reason = block_reason
        existing.path_hops = path_hops_json
        return existing

    # 尝试插入新记录，使用 savepoint (nested transaction) 处理并发冲突
    try:
        with session.begin_nested():
            row = AppFlow(
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
            )
            session.add(row)
            session.flush() # 强制触发唯一性检查
            
            # [DEBUG] 记录高频流插入
            if pkt_rate and pkt_rate > 1000:
                logger.info("Inserted HIGH RATE flow to DB: id=%s rate=%s", flow_id, pkt_rate)
                
        return row
    except Exception:
        # 如果插入失败（通常是由于并发导致的唯一性冲突），则再次查询
        # 注意：begin_nested() 失败会自动回滚到 savepoint，不需要手动 rollback session
        return session.query(AppFlow).filter_by(flow_id=flow_id).first()


def _auto_respond_to_dangerous_flow(flow_id: str, flow_data: Dict[str, Any], decision_level: str):
    """
    自动对高危流量进行响应（重定向或阻断）。
    """
    with _responded_flows_lock:
        if flow_id in _responded_flows:
            return
        _responded_flows.add(flow_id)

    try:
        client = get_controller_client()
        
        # 1. 检查网络拓扑中是否有 honeypot 类型的节点
        honeypot_ip = None
        try:
            topo = client.get_topology()
            nodes = topo.get("nodes", [])
            for node in nodes:
                if node.get("type") == "honeypot" and node.get("ip"):
                    honeypot_ip = node.get("ip")
                    logger.info("Found honeypot for redirection: %s", honeypot_ip)
                    break
        except Exception as e:
            logger.warning("Failed to fetch topology for honeypot check: %s", e)

        # 2. 确定最终动作
        # 如果决策是重定向但没找到蜜罐，则降级为阻断
        final_action = "block"
        if decision_level == DecisionLevel.REDIRECT.value:
            if honeypot_ip:
                final_action = "redirect"
            else:
                logger.info("No honeypot found in topology, downgrading REDIRECT to BLOCK for flow %s", flow_id)
                final_action = "block"
        elif decision_level == DecisionLevel.BLOCK.value:
            final_action = "block"
        else:
            # 其他情况（如 throttle）暂不处理或按需扩展
            return

        # 构造策略名称
        policy_name = f"Auto-{final_action.upper()}-{flow_id[:8]}"
        
        # 构造策略定义
        conditions = {}
        if flow_data.get("src_ip"):
            conditions["src_ip"] = flow_data.get("src_ip")
        if flow_data.get("dst_ip"):
            conditions["dst_ip"] = flow_data.get("dst_ip")
        if flow_data.get("protocol"):
            conditions["protocol"] = flow_data.get("protocol")
        if flow_data.get("dst_port"):
            conditions["dst_port"] = flow_data.get("dst_port")
            
        policy_def = {
            "name": policy_name,
            "type": "flow",
            "priority": 100,
            "conditions": conditions,
            "action": final_action,
        }
        
        if final_action == "redirect":
            policy_def["actions"] = {
                "primary_action": {
                    "action_type": "redirect",
                    "action_params": {
                        "targets": [{"ip": honeypot_ip}]
                    }
                }
            }
        
        # 3. 创建策略
        logger.info("Creating auto-response policy for flow %s: %s", flow_id, final_action)
        resp = client.create_policy(policy_def)
        policy_id = resp.get("policy_id")
        
        if policy_id:
            # 4. 应用策略
            client.apply_policy(policy_id, target_flows=[flow_id])
            logger.info("Successfully applied auto-response policy %s (%s) to flow %s", policy_id, final_action, flow_id)
            
            # 5. 记录系统事件
            now = datetime.now(timezone.utc).isoformat()
            
            # 根据动作类型发送不同的事件
            if final_action == "block":
                event_type = EventType.TRAFFIC_BLOCK
                event_data = {
                    "flow_id": flow_id,
                    "policy_id": policy_id,
                    "reason": f"AI detected {decision_level} traffic"
                }
            elif final_action == "redirect":
                event_type = EventType.TRAFFIC_REDIRECT
                event_data = {
                    "flow_id": flow_id,
                    "policy_id": policy_id,
                    "redirect_to": honeypot_ip,
                    "reason": f"AI detected {decision_level} traffic"
                }
            else:
                # Fallback to generic anomaly
                event_type = EventType.TRAFFIC_ANOMALY
                event_data = {
                    "flow_id": flow_id,
                    "type": "auto_mitigation",
                    "details": {
                        "policy_id": policy_id,
                        "action": final_action,
                        "reason": f"AI detected {decision_level} traffic",
                        "target": honeypot_ip if final_action == "redirect" else "blocked"
                    }
                }

            event = Event(
                event_type=event_type,
                timestamp=now,
                data=event_data
            )
            record_event_for_ui(event)
            
    except Exception as e:
        logger.error("Failed to auto-respond to dangerous flow %s: %s", flow_id, e)
        # 失败了可以从集合中移除，以便下次重试
        with _responded_flows_lock:
            if flow_id in _responded_flows:
                _responded_flows.remove(flow_id)


def _process_batch(tasks: List[FlowTask]) -> None:
    """
    在线程池中处理一批 Flow：
    1. 同步基础信息到 DB
    2. 执行 AI 推理
    3. 更新检测结果到 DB
    4. 推送 UI 事件
    """
    # 0. 任务去重（针对同一 flow_id，只保留最新的任务）
    unique_tasks_dict = {t.flow_id: t for t in tasks}
    unique_tasks = list(unique_tasks_dict.values())

    service = get_inference_service()
    flows = [t.flow for t in unique_tasks]

    # 1. 执行批量推理
    results = None
    error = None
    try:
        results = service.predict_batch(flows)
    except Exception as e:
        error = e
        logger.error("Flow batch prediction failed: %s", e, exc_info=True)

    # 2. 批量更新数据库和推送事件
    now = datetime.now(timezone.utc).isoformat()
    
    # SQLite 锁重试机制
    max_retries = 5
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            with session_scope() as session:
                for idx, task in enumerate(unique_tasks):
                    flow_id = task.flow_id
                    
                    # 同步基础信息
                    row = _sync_flow_to_db(session, task)
                    if row is None:
                        continue

                    # 更新检测结果
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
                        
                        # [DEBUG] 记录高频流检测结果
                        pkt_rate = task.flow.get("pkt_rate")
                        if pkt_rate and float(pkt_rate) > 1000:
                            msg = f"Detected HIGH RATE flow: id={flow_id} rate={pkt_rate} decision={decision_level} prob={prob}"
                            logger.info(msg)
                            print(f"!!! {msg} !!!")
                        
                        # 自动响应逻辑：如果决策为 REDIRECT 或 BLOCK，则触发自动响应
                        if decision_level in [DecisionLevel.REDIRECT.value, DecisionLevel.BLOCK.value]:
                            # 异步执行自动响应，避免阻塞批处理循环
                            threading.Thread(
                                target=_auto_respond_to_dangerous_flow,
                                args=(flow_id, task.flow, decision_level),
                                daemon=True
                            ).start()
                            
                    except Exception as e:
                        logger.error("Failed to record flow detection log: %s", e)

                    # 推送 UI 事件
                    try:
                        det_event = Event(
                            event_type=EventType.FLOW_DETECTION,
                            timestamp=now,
                            data={
                                "flow_id": flow_id,
                                "detect_status": status,
                                "label": label,
                                "prob": prob,
                                "decision_level": decision_level,
                                "flow_details": task.flow
                            }
                        )
                        # 传入当前 session 以避免创建嵌套 session 导致死锁
                        record_event_for_ui(det_event, session=session)
                    except Exception as e:
                        logger.debug("Failed to push flow detection event: %s", e)
            # 成功执行，跳出重试循环
            break
        except Exception as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logger.warning("Database locked, retrying batch update (attempt %d/%d)", attempt + 1, max_retries)
                time.sleep(retry_delay * (2 ** attempt)) # 指数退避
                continue
            logger.error("Failed to update flow detection results in batch: %s", e, exc_info=True)
            break


def _batcher_loop() -> None:
    """
    分发器主循环：
    - 从队列批量取 FlowTask
    - 提交到线程池处理
    """
    while not _stop_event.is_set():
        tasks: List[FlowTask] = []
        try:
            # 阻塞获取第一条，带超时以便检查停止信号
            first = _task_queue.get(timeout=1.0)
            tasks.append(first)
        except queue.Empty:
            continue
        except Exception:
            continue

        # 尝试凑齐一个 Batch
        try:
            while len(tasks) < BATCH_SIZE:
                next_task = _task_queue.get_nowait()
                tasks.append(next_task)
        except queue.Empty:
            pass

        if _executor:
            _executor.submit(_process_batch, tasks)


def stop_flow_detection_workers() -> None:
    """
    停止 Flow 检测服务。
    """
    global _workers_started, _executor, _batcher_thread
    if not _workers_started:
        return

    _stop_event.set()
    if _batcher_thread:
        _batcher_thread.join(timeout=2.0)
        _batcher_thread = None
    
    if _executor:
        _executor.shutdown(wait=True)
        _executor = None
    
    _workers_started = False
    _stop_event.clear()
    logger.info("Flow detection service stopped")


def start_flow_detection_workers() -> None:
    """
    启动 Flow 检测服务（线程池 + 分发器）。
    """
    global _workers_started, _executor, _batcher_thread
    if _workers_started:
        return

    _workers_started = True
    
    # 初始化线程池
    _executor = ThreadPoolExecutor(max_workers=WORKER_COUNT, thread_name_prefix="flow-detect-pool")
    
    # 启动分发器线程
    _batcher_thread = threading.Thread(target=_batcher_loop, name="flow-detect-batcher", daemon=True)
    _batcher_thread.start()
    
    logger.info("Flow detection service started with ThreadPoolExecutor (workers=%d)", WORKER_COUNT)


