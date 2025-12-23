"""
策略管理 API 路由。

严格按照 docs/api/README.md 和 docs/security-policies.md 定义的数据结构。
"""

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from .schemas import PolicyDetail, PolicySummary
from ..auth import require_permissions
from ..services.controller_client import (
    ControllerClientError,
    get_controller_client,
)

bp = Blueprint("policies", __name__, url_prefix="/api/policies")


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


@bp.get("")
@require_permissions("policy:read")
def list_policies():
    """
    列出所有策略。

    GET /api/policies
    Query params:
        - type: string (可选) 策略类型 (node, connection, flow)
        - status: string (可选) 策略状态 (active, disabled, pending)

    响应结构：
    {
        "policies": [PolicySummary, ...]
    }
    """
    policy_type: Optional[str] = request.args.get("type")
    status: Optional[str] = request.args.get("status")

    result = _call_controller(lambda c: c.list_policies(policy_type, status))
    return jsonify({"policies": result})


@bp.get("/<string:policy_id>")
@require_permissions("policy:read")
def get_policy(policy_id: str):
    """
    获取策略详情。

    GET /api/policies/{policy_id}

    响应结构：
    {
        "policy": PolicyDetail
    }
    """
    result = _call_controller(lambda c: c.get_policy(policy_id))
    return jsonify({"policy": result})


@bp.post("")
@require_permissions("policy:write")
def create_policy():
    """
    创建策略。

    POST /api/policies

    请求体：
    {
        "policy": PolicyDetail (部分字段)
    }

    响应结构：
    {
        "status": "success",
        "message": string,
        "policy_id": string
    }
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    policy_data = payload.get("policy", payload)

    result = _call_controller(lambda c: c.create_policy(policy_data))
    return jsonify(result), 201


@bp.put("/<string:policy_id>")
@require_permissions("policy:write")
def update_policy(policy_id: str):
    """
    更新策略。

    PUT /api/policies/{policy_id}

    请求体：
    {
        "policy": PolicyDetail (部分字段)
    }

    响应结构：
    {
        "status": "success",
        "message": string,
        "policy_id": string
    }
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    policy_data = payload.get("policy", payload)

    result = _call_controller(lambda c: c.update_policy(policy_id, policy_data))
    return jsonify(result)


@bp.delete("/<string:policy_id>")
@require_permissions("policy:write")
def delete_policy(policy_id: str):
    """
    删除策略。

    DELETE /api/policies/{policy_id}

    响应结构：
    {
        "status": "success",
        "message": string,
        "policy_id": string
    }
    """
    result = _call_controller(lambda c: c.delete_policy(policy_id))
    return jsonify(result)


@bp.post("/<string:policy_id>/apply")
@require_permissions("policy:execute")
def apply_policy(policy_id: str):
    """
    应用策略到目标对象。

    POST /api/policies/{policy_id}/apply

    请求体：
    {
        "target_nodes": [string],
        "target_links": [string],
        "target_flows": [string]
    }

    响应结构：
    {
        "status": "success",
        "message": string,
        "policy_id": string
    }
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    target_nodes: List[str] = payload.get("target_nodes", [])
    target_links: List[str] = payload.get("target_links", [])
    target_flows: List[str] = payload.get("target_flows", [])

    result = _call_controller(
        lambda c: c.apply_policy(policy_id, target_nodes, target_links, target_flows)
    )
    return jsonify(result)


@bp.post("/<string:policy_id>/revoke")
@require_permissions("policy:execute")
def revoke_policy(policy_id: str):
    """
    撤销已应用的策略。

    POST /api/policies/{policy_id}/revoke

    请求体：
    {
        "target_nodes": [string],
        "target_links": [string],
        "target_flows": [string]
    }

    响应结构：
    {
        "status": "success",
        "message": string,
        "policy_id": string
    }
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    target_nodes: List[str] = payload.get("target_nodes", [])
    target_links: List[str] = payload.get("target_links", [])
    target_flows: List[str] = payload.get("target_flows", [])

    result = _call_controller(
        lambda c: c.revoke_policy(policy_id, target_nodes, target_links, target_flows)
    )
    return jsonify(result)
