"""
控制层 WebSocket 事件订阅模块。

按照 docs/api/README.md 定义的 Event API 实现事件订阅。

支持的端点：
- /ws/network-status      网络状态更新
- /ws/traffic-anomalies   流量异常通知
- /ws/honeypot-alerts     蜜罐交互告警
- /ws/topology-changes    拓扑变更通知
- /ws/flow-updates        流状态更新
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import websockets
from websockets.exceptions import ConnectionClosed

from ..db import session_scope
from ..db.models import EventLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 事件类型定义
# ---------------------------------------------------------------------------


class EventType(str, Enum):
    """事件类型枚举。"""

    NETWORK_STATUS = "network_status_update"
    NODE_METRICS = "node_metrics_update"
    TRAFFIC_ANOMALY = "traffic_anomaly"
    HONEYPOT_INTERACTION = "honeypot_interaction"
    TOPOLOGY_CHANGE = "topology_change"
    FLOW_UPDATE = "flow_update"
    FLOW_DETECTION = "flow_detection_result"


@dataclass
class Event:
    """标准化事件结构。"""

    event_type: EventType
    timestamp: str
    data: Dict[str, Any]
    raw: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 面向 UI 的最近事件缓存（内存环形缓冲区）
# ---------------------------------------------------------------------------

_ui_events_lock = threading.Lock()
_ui_events: List[Event] = []
_ui_events_max_len = 200


def record_event_for_ui(event: Event) -> None:
    """
    记录事件到内存缓存，供前端查询最近事件使用。

    简单环形缓冲：只保留最近 _ui_events_max_len 条。
    同时将重要事件持久化到数据库。
    """
    # 1. 自动拆分逻辑：如果 network_status_update 包含指标，则拆分出 node_metrics_update
    if event.event_type == EventType.NETWORK_STATUS:
        data = event.data
        metrics = {}
        # 提取可能的指标字段
        for field_name in ["cpu_usage", "memory_usage", "network_throughput"]:
            if field_name in data:
                metrics[field_name] = data.pop(field_name)
        
        if metrics:
            # 构造并推送指标事件（不进入 _ui_events 缓存，也不持久化，仅实时推送）
            metrics_event = {
                "type": EventType.NODE_METRICS.value,
                "timestamp": event.timestamp,
                "data": {
                    "node_id": data.get("node_id"),
                    "metrics": metrics
                }
            }
            try:
                from .ui_events_ws import enqueue_ui_event
                enqueue_ui_event(metrics_event)
            except Exception:
                pass
            
            # 如果 data 中只剩下 node_id 了（没有 status），则不再继续处理原始事件
            if len(data) <= 1 and "node_id" in data:
                return

    # 对 FLOW_UPDATE 事件，默认补充 detect_status=pending，方便前端展示
    if event.event_type == EventType.FLOW_UPDATE:
        try:
            event.data.setdefault("detect_status", "pending")
        except Exception:
            pass

    with _ui_events_lock:
        _ui_events.append(event)
        if len(_ui_events) > _ui_events_max_len:
            del _ui_events[0 : len(_ui_events) - _ui_events_max_len]

    # 持久化逻辑：将非 FLOW_UPDATE 的重要事件存入数据库
    if event.event_type != EventType.FLOW_UPDATE:
        try:
            with session_scope() as session:
                # 提取相关资源 ID
                related_resource = None
                data = event.data
                etype = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
                
                if etype == "network_status_update":
                    related_resource = data.get("node_id")
                elif etype == "traffic_anomaly":
                    related_resource = data.get("flow_id")
                elif etype == "honeypot_interaction":
                    related_resource = data.get("source_ip")
                elif etype == "topology_change":
                    related_resource = data.get("change_type")
                elif etype == "flow_detection_result":
                    related_resource = data.get("flow_id")

                # 确定严重程度
                severity = "info"
                if etype in ("traffic_anomaly", "honeypot_interaction"):
                    severity = "warning"
                elif etype == "flow_detection_result":
                    detect_status = data.get("detect_status")
                    if detect_status == "dangerous":
                        severity = "high"
                    elif detect_status == "suspicious":
                        severity = "warning"
                
                log = EventLog(
                    event_type=etype,
                    source="ai_model" if etype == "flow_detection_result" else "controller",
                    severity=severity,
                    payload_snapshot=json.dumps(event.data, ensure_ascii=False),
                    related_resource=related_resource,
                    processed_by="event_subscriber"
                )
                session.add(log)
        except Exception as e:
            logger.error("Failed to persist event log: %s", e)

    # 异步推送给 UI WebSocket 客户端
    try:
        from .ui_events_ws import enqueue_ui_event

        enqueue_ui_event(
            {
                "type": event.event_type.value,
                "timestamp": event.timestamp,
                "data": event.data,
            }
        )
    except Exception:
        # 不影响主流程
        pass


def get_recent_events(limit: int = 100, event_types: Optional[Set[EventType]] = None) -> List[Dict[str, Any]]:
    """
    获取最近的事件列表，按时间顺序返回，转换为可 JSON 序列化的 dict。
    """
    with _ui_events_lock:
        events = list(_ui_events[-limit:])

    if event_types is not None:
        events = [e for e in events if e.event_type in event_types]

    return [
        {
            "type": e.event_type.value,
            "timestamp": e.timestamp,
            "data": e.data,
        }
        for e in events
    ]


# ---------------------------------------------------------------------------
# 事件处理器类型
# ---------------------------------------------------------------------------

EventHandler = Callable[[Event], None]


# ---------------------------------------------------------------------------
# WebSocket 端点配置
# ---------------------------------------------------------------------------

WS_ENDPOINTS: Dict[EventType, str] = {
    EventType.NETWORK_STATUS: "/ws/network-status",
    EventType.NODE_METRICS: "/ws/node-metrics",
    EventType.TRAFFIC_ANOMALY: "/ws/traffic-anomalies",
    EventType.HONEYPOT_INTERACTION: "/ws/honeypot-alerts",
    EventType.TOPOLOGY_CHANGE: "/ws/topology-changes",
    EventType.FLOW_UPDATE: "/ws/flow-updates",
}


# ---------------------------------------------------------------------------
# 单个端点的订阅连接
# ---------------------------------------------------------------------------


class EndpointSubscriber:
    """
    单个 WebSocket 端点的订阅连接。

    负责：
    - 建立和维护 WebSocket 连接
    - 指数退避重连
    - 解析事件并分发给处理器
    """

    def __init__(
        self,
        base_url: str,
        endpoint: str,
        event_type: EventType,
        handlers: List[EventHandler],
        max_retries: int = 10,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._endpoint = endpoint
        self._event_type = event_type
        self._handlers = handlers
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay

        self._running = False
        self._retry_count = 0
        self._ws: Optional[websockets.WebSocketClientProtocol] = None

    @property
    def url(self) -> str:
        return f"{self._base_url}{self._endpoint}"

    async def connect(self) -> None:
        """建立 WebSocket 连接。"""
        self._running = True
        self._retry_count = 0

        while self._running:
            try:
                async with websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    self._ws = ws
                    self._retry_count = 0
                    logger.info("Connected to %s", self.url)
                    await self._receive_loop(ws)
            except ConnectionClosed as e:
                logger.warning("Connection to %s closed: %s", self.url, e)
            except Exception as e:
                logger.error("Error connecting to %s: %s", self.url, e)

            if not self._running:
                break

            # 指数退避重连
            self._retry_count += 1
            if self._retry_count > self._max_retries:
                logger.error("Max retries exceeded for %s", self.url)
                break

            delay = min(self._base_delay * (2 ** (self._retry_count - 1)), self._max_delay)
            logger.info("Reconnecting to %s in %.1f seconds...", self.url, delay)
            await asyncio.sleep(delay)

    async def _receive_loop(self, ws: websockets.WebSocketClientProtocol) -> None:
        """接收消息循环。"""
        async for message in ws:
            try:
                raw = json.loads(message)
                event = self._parse_event(raw)
                self._dispatch(event)
            except json.JSONDecodeError as e:
                logger.warning("Failed to parse message: %s", e)
            except Exception as e:
                logger.error("Error processing message: %s", e)

    def _parse_event(self, raw: Dict[str, Any]) -> Event:
        """解析原始消息为标准化事件。"""
        return Event(
            event_type=self._event_type,
            timestamp=raw.get("timestamp", ""),
            data=raw.get("data", {}),
            raw=raw,
        )

    def _dispatch(self, event: Event) -> None:
        """分发事件给所有处理器。"""
        for handler in self._handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Handler error: %s", e)

    async def disconnect(self) -> None:
        """断开连接。"""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None


# ---------------------------------------------------------------------------
# 事件订阅管理器
# ---------------------------------------------------------------------------


class EventSubscriberManager:
    """
    事件订阅管理器。

    负责：
    - 管理多个端点的订阅
    - 注册/注销事件处理器
    - 启动/停止订阅
    """

    def __init__(self, ws_base_url: str) -> None:
        self._ws_base_url = ws_base_url
        self._handlers: Dict[EventType, List[EventHandler]] = {et: [] for et in EventType}
        self._subscribers: Dict[EventType, EndpointSubscriber] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def register_handler(self, event_type: EventType, handler: EventHandler) -> None:
        """注册事件处理器。"""
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def unregister_handler(self, event_type: EventType, handler: EventHandler) -> None:
        """注销事件处理器。"""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def subscribe(self, event_types: Optional[Set[EventType]] = None) -> None:
        """
        订阅指定类型的事件。

        如果 event_types 为 None，则订阅所有类型。
        """
        if event_types is None:
            event_types = set(EventType)

        for et in event_types:
            # Skip internal events that don't have external WS endpoints
            if et not in WS_ENDPOINTS:
                continue

            if et not in self._subscribers:
                endpoint = WS_ENDPOINTS[et]
                subscriber = EndpointSubscriber(
                    base_url=self._ws_base_url,
                    endpoint=endpoint,
                    event_type=et,
                    handlers=self._handlers[et],
                )
                self._subscribers[et] = subscriber

    def start(self, event_types: Optional[Set[EventType]] = None) -> None:
        """
        在后台线程中启动事件订阅。
        """
        if self._running:
            return

        self.subscribe(event_types)
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        """在独立线程中运行事件循环。"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        tasks = [sub.connect() for sub in self._subscribers.values()]
        if tasks:
            self._loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))

    def stop(self) -> None:
        """停止所有订阅。"""
        self._running = False
        if self._loop:
            for sub in self._subscribers.values():
                asyncio.run_coroutine_threadsafe(sub.disconnect(), self._loop)
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._subscribers.clear()


# ---------------------------------------------------------------------------
# 全局管理器实例
# ---------------------------------------------------------------------------

_manager_instance: Optional[EventSubscriberManager] = None
_manager_lock = threading.Lock()


def get_event_subscriber(ws_base_url: Optional[str] = None) -> EventSubscriberManager:
    """获取全局事件订阅管理器单例。"""
    global _manager_instance
    with _manager_lock:
        if _manager_instance is None:
            if ws_base_url is None:
                from flask import current_app
                ws_base_url = current_app.config.get("CONTROLLER_WS_BASE_URL", "ws://localhost:8000")
            _manager_instance = EventSubscriberManager(ws_base_url)
        return _manager_instance


def reset_event_subscriber() -> None:
    """重置全局事件订阅管理器。"""
    global _manager_instance
    with _manager_lock:
        if _manager_instance:
            _manager_instance.stop()
        _manager_instance = None
