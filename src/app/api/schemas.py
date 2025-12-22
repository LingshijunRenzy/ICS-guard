from typing import List, TypedDict


class Node(TypedDict):
    id: str
    name: str
    type: str
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


class PolicyDetail(TypedDict):
    id: str
    name: str
    description: str
    type: str
    subtype: str
    status: str
    priority: int
    scope: dict
    conditions: dict
    actions: dict
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


