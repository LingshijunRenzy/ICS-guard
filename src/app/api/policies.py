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


def _try_controller_call(func, *args, **kwargs) -> Any:
    """尝试调用控制层，失败时返回 None。"""
    try:
        client = get_controller_client()
        return func(client, *args, **kwargs)
    except ControllerClientError:
        return None
    except Exception:
        return None


def _demo_policy_summary() -> List[PolicySummary]:
    """演示用策略列表。"""
    return [
        {
            "id": "flow-redirect-001",
            "name": "Suspicious-Traffic-Redirect",
            "type": "flow",
            "status": "active",
            "priority": 75,
            "metadata": {"created_at": "2025-01-01T00:00:00Z"},
        },
        {
            "id": "node-access-001",
            "name": "PLC-Access-Control",
            "type": "node",
            "status": "active",
            "priority": 100,
            "metadata": {"created_at": "2025-01-01T00:00:00Z"},
        },
    ]


def _demo_policy_detail(policy_id: str) -> PolicyDetail:
    """演示用策略详情。"""
    demo_policies: Dict[str, PolicyDetail] = {
        "flow-redirect-001": {
            "id": "flow-redirect-001",
            "name": "Suspicious-Traffic-Redirect",
            "description": "将可疑流量重定向至蜜罐",
            "type": "flow",
            "subtype": "traffic_redirect",
            "status": "active",
            "priority": 75,
            "scope": {"target_type": "ip_range", "target_identifier": "192.168.1.0/24"},
            "conditions": {"suspicion_level": "high"},
            "actions": {
                "primary_action": "redirect",
                "secondary_actions": [
                    {"action_type": "redirect", "redirect_target": "honeypot-01"},
                    {"action_type": "log", "log_level": "info", "log_message": "重定向可疑流量至蜜罐"},
                ],
            },
            "monitoring": {"enable_statistics": True, "sample_interval_seconds": 60},
            "metadata": {"created_at": "2025-01-01T00:00:00Z", "version": 1},
        },
        "node-access-001": {
            "id": "node-access-001",
            "name": "PLC-Access-Control",
            "description": "限制对PLC-01的访问",
            "type": "node",
            "subtype": "access_control",
            "status": "active",
            "priority": 100,
            "scope": {"target_type": "device", "target_identifier": "PLC-01"},
            "conditions": {
                "allowed_ips": ["192.168.1.10", "192.168.1.20"],
                "denied_ips": ["192.168.1.30"],
            },
            "actions": {
                "primary_action": "allow",
                "secondary_actions": [
                    {"action_type": "log", "log_level": "info", "log_message": "访问PLC-01"},
                ],
            },
            "monitoring": {},
            "metadata": {"created_at": "2025-01-01T00:00:00Z", "version": 1},
        },
    }
    return demo_policies.get(policy_id, {
        "id": policy_id,
        "name": f"Policy-{policy_id}",
        "description": "Unknown policy",
        "type": "unknown",
        "subtype": "",
        "status": "unknown",
        "priority": 0,
        "scope": {},
        "conditions": {},
        "actions": {"primary_action": "allow"},
        "monitoring": {},
        "metadata": {},
    })


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

    result = _try_controller_call(lambda c: c.list_policies(policy_type, status))
    if result is not None:
        return jsonify({"policies": result})

    # 降级到演示数据
    policies = _demo_policy_summary()
    # 应用过滤
    if policy_type:
        policies = [p for p in policies if p.get("type") == policy_type]
    if status:
        policies = [p for p in policies if p.get("status") == status]
    return jsonify({"policies": policies})


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
    result = _try_controller_call(lambda c: c.get_policy(policy_id))
    if result is not None:
        return jsonify({"policy": result})

    return jsonify({"policy": _demo_policy_detail(policy_id)})


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

    result = _try_controller_call(lambda c: c.create_policy(policy_data))
    if result is not None:
        return jsonify(result), 201

    # 演示模式：返回成功响应
    policy_id = policy_data.get("id", "new-policy-001")
    return jsonify({
        "status": "success",
        "message": "Policy created successfully (demo mode)",
        "policy_id": policy_id,
    }), 201


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

    result = _try_controller_call(lambda c: c.update_policy(policy_id, policy_data))
    if result is not None:
        return jsonify(result)

    return jsonify({
        "status": "success",
        "message": "Policy updated successfully (demo mode)",
        "policy_id": policy_id,
    })


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
    result = _try_controller_call(lambda c: c.delete_policy(policy_id))
    if result is not None:
        return jsonify(result)

    return jsonify({
        "status": "success",
        "message": "Policy deleted successfully (demo mode)",
        "policy_id": policy_id,
    })


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

    result = _try_controller_call(
        lambda c: c.apply_policy(policy_id, target_nodes, target_links, target_flows)
    )
    if result is not None:
        return jsonify(result)

    return jsonify({
        "status": "success",
        "message": "Policy applied successfully (demo mode)",
        "policy_id": policy_id,
    })


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

    result = _try_controller_call(
        lambda c: c.revoke_policy(policy_id, target_nodes, target_links, target_flows)
    )
    if result is not None:
        return jsonify(result)

    return jsonify({
        "status": "success",
        "message": "Policy revoked successfully (demo mode)",
        "policy_id": policy_id,
    })
