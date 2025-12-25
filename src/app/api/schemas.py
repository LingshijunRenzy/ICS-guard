from typing import List, TypedDict, Optional


class Node(TypedDict):
    id: str
    name: str
    type: str
    zone: str
    ip: str
    status: str


class Link(TypedDict):
    id: str
    source: str
    target: str
    bandwidth: int
    status: str


class TopologyResponse(TypedDict):
    nodes: List[Node]
    links: List[Link]


class NodeStatus(TypedDict):
    node_id: str
    status: str
    last_updated: str
    metrics: dict


class LinkStatus(TypedDict):
    link_id: str
    status: str
    last_updated: str
    metrics: dict


class PolicySummary(TypedDict):
    id: str
    name: str
    type: str
    status: str
    priority: int
    metadata: dict


class PolicyEffect(TypedDict, total=False):
    id: str
    name: str
    action: str  # allow | block | redirect | throttle | isolate | inspect | log
    priority: int
    matched_at: str  # ISO 8601
    result: str  # applied | skipped | error
    reason: Optional[str]  # 失败或跳过原因（可选）


class RedirectInfo(TypedDict, total=False):
    dst_ip: str
    dst_port: int
    node_id: Optional[str]


class FinalDestination(TypedDict, total=False):
    dst_ip: str
    dst_port: int


class PathHop(TypedDict, total=False):
    node_id: str
    ip: Optional[str]
    type: Optional[str]
    entered_at: Optional[str]  # ISO 8601
    left_at: Optional[str]  # ISO 8601


class FlowInfo(TypedDict):
    id: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    start_time: str
    end_time: str
    duration: float
    pkt_count: int
    byte_count: int
    pkt_rate: float
    byte_rate: float
    func_code_entropy: float
    reg_addr_std: float
    status: str
    policy_effects: Optional[List[PolicyEffect]]  # (可选) 记录策略命中与动作结果
    redirect_to: Optional[RedirectInfo]  # (可选) 重定向目标
    final_dst: Optional[FinalDestination]  # (可选) 实际送达/尝试的终点
    blocked: Optional[bool]  # (可选) 是否被阻断
    blocked_at: Optional[str]  # (可选) 阻断时间 (ISO 8601)
    block_reason: Optional[str]  # (可选) 阻断原因
    path_hops: Optional[List[PathHop]]  # (可选) 表示经过的节点路径


class EventLogSchema(TypedDict):
    id: int
    type: str
    source: str
    severity: str
    payload: Optional[str]
    resource: Optional[str]
    processed_by: Optional[str]
    timestamp: str


class FlowDetectionLogSchema(TypedDict):
    id: int
    flow_id: str
    prob: float
    label: Optional[str]
    anomaly_score: float
    decision_level: str
    timestamp: str
    model_version: Optional[str]


class ActionParams(TypedDict, total=False):
    """动作参数基类，具体参数根据action_type而定"""
    pass


class RateLimitParams(TypedDict, total=False):
    bandwidth_mbps: float  # 必填，>0
    packets_per_second: Optional[int]
    direction: Optional[str]  # ingress|egress|both
    burst_packets: Optional[int]
    burst_bytes: Optional[int]
    strategy: Optional[str]  # drop|queue
    smoothing: Optional[str]  # token_bucket|leaky_bucket


class LogActionParams(ActionParams):
    log_level: str  # info, warning, alert, error
    log_message: str


class ThrottleActionParams(ActionParams):
    rate_limit: RateLimitParams


class RedirectTarget(TypedDict):
    ip: str
    port: int


class RedirectActionParams(ActionParams):
    targets: List[RedirectTarget]  # [{"ip": "10.0.0.99", "port": 502}]
    redirect_target: Optional[str]  # 用于次要动作中的蜜罐标识符


class AlertActionParams(ActionParams):
    alert_level: str  # info, warning, high, critical
    notification_channels: Optional[List[str]]  # email, syslog


class BlockActionParams(ActionParams):
    blocked_protocols: Optional[List[str]]


class DisableActionParams(ActionParams):
    reason: Optional[str]


class ShutdownActionParams(ActionParams):
    notice: Optional[str]


class Action(TypedDict):
    action_type: str
    action_params: Optional[ActionParams]


class PolicyActions(TypedDict):
    primary_action: Action
    secondary_actions: List[Action]


class PolicyScope(TypedDict):
    target_type: str  # device, connection, protocol, ip_range
    target_identifier: str


class PolicyDetail(TypedDict):
    id: str
    name: str
    description: str
    type: str
    subtype: str
    status: str
    priority: int
    scope: PolicyScope
    conditions: dict
    actions: PolicyActions
    monitoring: dict
    metadata: dict


class AlertItem(TypedDict):
    id: str
    timestamp: str
    type: str
    severity: str
    source_ip: str
    description: str


class HoneypotLogItem(TypedDict):
    id: str
    timestamp: str
    source_ip: str
    request: str
    response: str


