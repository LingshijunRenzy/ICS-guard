"""
拓扑与状态 API 路由。

严格按照 docs/api/README.md 定义的数据结构。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify

from .schemas import Link, LinkStatus, Node, NodeStatus, TopologyResponse
from ..auth import require_permissions
from ..services.controller_client import (
    ControllerClient,
    ControllerClientError,
    get_controller_client,
)

bp = Blueprint("topology", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _demo_timestamp() -> str:
    """生成当前 UTC 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


def _demo_topology() -> TopologyResponse:
    """演示用拓扑数据。"""
    nodes: List[Node] = [
        {"id": "sw1", "name": "Switch1", "type": "switch", "ip": "10.0.0.1", "status": "online"},
        {"id": "plc1", "name": "PLC1", "type": "plc", "ip": "10.0.0.10", "status": "online"},
        {"id": "hp1", "name": "Honeypot1", "type": "honeypot", "ip": "10.0.0.20", "status": "online"},
    ]
    links: List[Link] = [
        {"id": "link-sw1-plc1", "source": "sw1", "target": "plc1", "bandwidth": 100, "status": "active"},
        {"id": "link-sw1-hp1", "source": "sw1", "target": "hp1", "bandwidth": 100, "status": "active"},
    ]
    return {"nodes": nodes, "links": links}


def _demo_node_status(node_id: str) -> NodeStatus:
    """演示用节点状态数据。"""
    demo_data: Dict[str, NodeStatus] = {
        "plc1": {
            "node_id": "plc1",
            "status": "online",
            "last_updated": _demo_timestamp(),
            "metrics": {"cpu_usage": 12.3, "memory_usage": 40.1, "network_throughput": 5.2},
        },
        "hp1": {
            "node_id": "hp1",
            "status": "online",
            "last_updated": _demo_timestamp(),
            "metrics": {"cpu_usage": 8.1, "memory_usage": 30.5, "network_throughput": 1.2},
        },
        "sw1": {
            "node_id": "sw1",
            "status": "online",
            "last_updated": _demo_timestamp(),
            "metrics": {"cpu_usage": 5.0, "memory_usage": 20.0, "network_throughput": 50.0},
        },
    }
    return demo_data.get(node_id, {
        "node_id": node_id,
        "status": "unknown",
        "last_updated": _demo_timestamp(),
        "metrics": {},
    })


def _demo_link_status(link_id: str) -> LinkStatus:
    """演示用连接状态数据。"""
    demo_data: Dict[str, LinkStatus] = {
        "sw1-plc1": {
            "link_id": "sw1-plc1",
            "status": "active",
            "last_updated": _demo_timestamp(),
            "metrics": {"bandwidth_usage": 10.5, "latency": 1.2, "packet_loss": 0.0},
        },
        "sw1-hp1": {
            "link_id": "sw1-hp1",
            "status": "active",
            "last_updated": _demo_timestamp(),
            "metrics": {"bandwidth_usage": 2.0, "latency": 0.8, "packet_loss": 0.0},
        },
    }
    return demo_data.get(link_id, {
        "link_id": link_id,
        "status": "unknown",
        "last_updated": _demo_timestamp(),
        "metrics": {},
    })


def _is_demo_mode() -> bool:
    """判断是否为演示模式（控制层不可用时自动降级）。"""
    return current_app.config.get("DEMO_MODE", False)


def _try_controller_call(func, *args, **kwargs) -> Any:
    """尝试调用控制层，失败时返回 None。"""
    try:
        client = get_controller_client()
        return func(client, *args, **kwargs)
    except ControllerClientError:
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@bp.get("/topology")
def get_topology():
    """
    获取网络拓扑信息。

    GET /api/topology

    响应结构：
    {
        "nodes": [Node, ...],
        "links": [Link, ...]
    }
    """
    # 尝试从控制层获取
    result = _try_controller_call(lambda c: c.get_topology())
    if result is not None:
        return jsonify(result)

    # 降级到演示数据
    return jsonify(_demo_topology())


@bp.get("/nodes/<string:node_id>/status")
def get_node_status(node_id: str):
    """
    获取节点状态。

    GET /api/nodes/{node_id}/status

    响应结构：
    {
        "node_id": string,
        "status": string,
        "last_updated": string (ISO 8601),
        "metrics": {
            "cpu_usage": number,
            "memory_usage": number,
            "network_throughput": number
        }
    }
    """
    # 尝试从控制层获取
    result = _try_controller_call(lambda c: c.get_node_status(node_id))
    if result is not None:
        return jsonify({
            "node_id": result.node_id,
            "status": result.status,
            "last_updated": result.last_updated,
            "metrics": result.metrics,
        })

    # 降级到演示数据
    return jsonify(_demo_node_status(node_id))


@bp.get("/links/<string:link_id>/status")
def get_link_status(link_id: str):
    """
    获取连接状态。

    GET /api/links/{link_id}/status

    响应结构：
    {
        "link_id": string,
        "status": string,
        "last_updated": string (ISO 8601),
        "metrics": {
            "bandwidth_usage": number,
            "latency": number,
            "packet_loss": number
        }
    }
    """
    # 尝试从控制层获取
    result = _try_controller_call(lambda c: c.get_link_status(link_id))
    if result is not None:
        return jsonify({
            "link_id": result.link_id,
            "status": result.status,
            "last_updated": result.last_updated,
            "metrics": result.metrics,
        })

    # 降级到演示数据
    return jsonify(_demo_link_status(link_id))


# ---------------------------------------------------------------------------
# 节点操作
# ---------------------------------------------------------------------------


@bp.post("/nodes/<string:node_id>/start")
@require_permissions("node:control")
def start_node(node_id: str):
    """
    启动节点。

    POST /api/nodes/{node_id}/start
    """
    result = _try_controller_call(lambda c: c.start_node(node_id))
    if result is not None:
        return jsonify(result)
    return jsonify({
        "status": "success",
        "message": f"Node {node_id} start requested (demo mode)",
        "node_id": node_id,
    })


@bp.post("/nodes/<string:node_id>/stop")
@require_permissions("node:control")
def stop_node(node_id: str):
    """
    停止节点。

    POST /api/nodes/{node_id}/stop
    """
    result = _try_controller_call(lambda c: c.stop_node(node_id))
    if result is not None:
        return jsonify(result)
    return jsonify({
        "status": "success",
        "message": f"Node {node_id} stop requested (demo mode)",
        "node_id": node_id,
    })


@bp.post("/nodes/<string:node_id>/restart")
@require_permissions("node:control")
def restart_node(node_id: str):
    """
    重启节点。

    POST /api/nodes/{node_id}/restart
    """
    result = _try_controller_call(lambda c: c.restart_node(node_id))
    if result is not None:
        return jsonify(result)
    return jsonify({
        "status": "success",
        "message": f"Node {node_id} restart requested (demo mode)",
        "node_id": node_id,
    })


# ---------------------------------------------------------------------------
# 连接操作
# ---------------------------------------------------------------------------


@bp.post("/links/<string:link_id>/enable")
@require_permissions("link:control")
def enable_link(link_id: str):
    """
    启用连接。

    POST /api/links/{link_id}/enable
    """
    result = _try_controller_call(lambda c: c.enable_link(link_id))
    if result is not None:
        return jsonify(result)
    return jsonify({
        "status": "success",
        "message": f"Link {link_id} enabled (demo mode)",
        "link_id": link_id,
    })


@bp.post("/links/<string:link_id>/disable")
@require_permissions("link:control")
def disable_link(link_id: str):
    """
    禁用连接。

    POST /api/links/{link_id}/disable
    """
    result = _try_controller_call(lambda c: c.disable_link(link_id))
    if result is not None:
        return jsonify(result)
    return jsonify({
        "status": "success",
        "message": f"Link {link_id} disabled (demo mode)",
        "link_id": link_id,
    })


# ---------------------------------------------------------------------------
# 统计
# ---------------------------------------------------------------------------


@bp.get("/nodes/stats")
def get_node_stats():
    """
    获取节点性能统计。

    GET /api/nodes/stats
    """
    from flask import request
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")

    result = _try_controller_call(lambda c: c.get_node_stats(start_time, end_time))
    if result is not None:
        return jsonify({"stats": result})

    # 演示数据
    return jsonify({
        "stats": [
            {
                "node_id": "plc1",
                "timestamp": _demo_timestamp(),
                "cpu_usage": 12.3,
                "memory_usage": 40.1,
                "network_throughput": 5.2,
            },
        ]
    })


@bp.get("/links/stats")
def get_link_stats():
    """
    获取连接性能统计。

    GET /api/links/stats
    """
    from flask import request
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")

    result = _try_controller_call(lambda c: c.get_link_stats(start_time, end_time))
    if result is not None:
        return jsonify({"stats": result})

    # 演示数据
    return jsonify({
        "stats": [
            {
                "link_id": "sw1-plc1",
                "timestamp": _demo_timestamp(),
                "bandwidth_usage": 10.5,
                "latency": 1.2,
                "packet_loss": 0.0,
            },
        ]
    })
