"""
拓扑与状态 API 路由。

严格按照 docs/api/README.md 定义的数据结构。
"""

from typing import Any

from flask import Blueprint, jsonify

from ..auth import require_permissions
from ..services.controller_client import get_controller_client

bp = Blueprint("topology", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _call_controller(func, *args, **kwargs) -> Any:
    """调用控制层 API，失败时抛出异常。"""
    client = get_controller_client()
    return func(client, *args, **kwargs)


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@bp.get("/topology")
@require_permissions("topology:read")
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
    result = _call_controller(lambda c: c.get_topology())
    return jsonify(result)


@bp.get("/nodes/<string:node_id>/status")
@require_permissions("topology:read")
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
    result = _call_controller(lambda c: c.get_node_status(node_id))
    return jsonify({
        "node_id": result.node_id,
        "status": result.status,
        "last_updated": result.last_updated,
        "metrics": result.metrics,
    })


@bp.get("/links/<string:link_id>/status")
@require_permissions("topology:read")
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
    result = _call_controller(lambda c: c.get_link_status(link_id))
    return jsonify({
        "link_id": result.link_id,
        "status": result.status,
        "last_updated": result.last_updated,
        "metrics": result.metrics,
    })


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
    result = _call_controller(lambda c: c.start_node(node_id))
    return jsonify(result)


@bp.post("/nodes/<string:node_id>/stop")
@require_permissions("node:control")
def stop_node(node_id: str):
    """
    停止节点。

    POST /api/nodes/{node_id}/stop
    """
    result = _call_controller(lambda c: c.stop_node(node_id))
    return jsonify(result)


@bp.post("/nodes/<string:node_id>/restart")
@require_permissions("node:control")
def restart_node(node_id: str):
    """
    重启节点。

    POST /api/nodes/{node_id}/restart
    """
    result = _call_controller(lambda c: c.restart_node(node_id))
    return jsonify(result)


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
    result = _call_controller(lambda c: c.enable_link(link_id))
    return jsonify(result)


@bp.post("/links/<string:link_id>/disable")
@require_permissions("link:control")
def disable_link(link_id: str):
    """
    禁用连接。

    POST /api/links/{link_id}/disable
    """
    result = _call_controller(lambda c: c.disable_link(link_id))
    return jsonify(result)


# ---------------------------------------------------------------------------
# 统计
# ---------------------------------------------------------------------------


@bp.get("/nodes/stats")
@require_permissions("topology:read")
def get_node_stats():
    """
    获取节点性能统计。

    GET /api/nodes/stats
    """
    from flask import request
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")

    result = _call_controller(lambda c: c.get_node_stats(start_time, end_time))
    return jsonify({"stats": result})


@bp.get("/links/stats")
@require_permissions("topology:read")
def get_link_stats():
    """
    获取连接性能统计。

    GET /api/links/stats
    """
    from flask import request
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")

    result = _call_controller(lambda c: c.get_link_stats(start_time, end_time))
    return jsonify({"stats": result})
