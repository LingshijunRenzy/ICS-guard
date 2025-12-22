"""
角色查询 API（仅用于前端用户管理页面选择角色）。

GET /api/roles
需要 user:manage 权限。
"""

from typing import Any, Dict, List

from flask import Blueprint, jsonify

from ..auth import require_permissions
from ..db import session_scope
from ..db.models import Role

bp = Blueprint("roles", __name__, url_prefix="/api/roles")


@bp.get("")
@require_permissions("user:manage")
def list_roles():
    """
    列出所有角色。

    GET /api/roles
    响应：
    {
        "roles": [
            {"id": 1, "name": "admin", "display_name": "...", "description": "...", "is_system": true},
            ...
        ]
    }
    """
    with session_scope() as session:
        roles: List[Role] = session.query(Role).order_by(Role.id.asc()).all()
        data: List[Dict[str, Any]] = [
            {
                "id": r.id,
                "name": r.name,
                "display_name": r.display_name,
                "description": r.description,
                "is_system": r.is_system,
            }
            for r in roles
        ]
        return jsonify({"roles": data})


__all__ = ["bp"]


