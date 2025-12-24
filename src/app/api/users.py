"""
应用层用户管理 API。

对应 docs/rbac-design.md 中的 2.8 用户管理：
- 列出用户  GET    /api/users
- 创建用户  POST   /api/users
- 更新用户  PUT    /api/users/{id}
- 删除用户  DELETE /api/users/{id}

所有接口均要求 user:manage 权限。
"""

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from ..auth import require_permissions
from ..db import session_scope
from ..db.models import Role, User
from ..utils.audit import record_audit_log

bp = Blueprint("users", __name__, url_prefix="/api/users")


def _user_to_dict(user: User) -> Dict[str, Any]:
    """将 User ORM 对象转换为对前端友好的字典。"""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "roles": [r.name for r in user.roles],
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


@bp.get("")
@require_permissions("user:manage")
def list_users():
    """
    列出所有用户。

    GET /api/users
    响应：
    {
        "users": [ {id, username, email, display_name, is_active, roles, ...}, ... ]
    }
    """
    with session_scope() as session:
        users: List[User] = session.query(User).order_by(User.id.asc()).all()
        return jsonify({"users": [_user_to_dict(u) for u in users]})


@bp.post("")
@require_permissions("user:manage")
def create_user():
    """
    创建用户。

    POST /api/users
    请求体：
    {
        "username": "admin",
        "password": "xxx",
        "email": "admin@example.com",
        "display_name": "Admin",
        "is_active": true,
        "roles": ["admin", "operator"]
    }
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    email: Optional[str] = payload.get("email")
    display_name: Optional[str] = payload.get("display_name")
    is_active: bool = bool(payload.get("is_active", True))
    role_names: List[str] = payload.get("roles") or []

    if not username or not password:
        return (
            jsonify({"error": "invalid_request", "message": "username and password are required"}),
            400,
        )

    with session_scope() as session:
        # 唯一性检查
        if session.query(User).filter_by(username=username).first():
            return jsonify({"error": "conflict", "message": "username already exists"}), 409

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            email=email,
            display_name=display_name,
            is_active=is_active,
        )

        if role_names:
            roles = session.query(Role).filter(Role.name.in_(role_names)).all()
            user.roles = roles

        session.add(user)
        session.flush()  # 获取自增 ID

        record_audit_log(
            action="USER_CREATE",
            resource="user",
            resource_id=str(user.id),
            payload={"username": username, "email": email, "roles": role_names},
            status="success"
        )

        return jsonify({"user": _user_to_dict(user)}), 201


@bp.put("/<int:user_id>")
@require_permissions("user:manage")
def update_user(user_id: int):
    """
    更新用户。

    PUT /api/users/{id}
    支持更新：email, display_name, is_active, roles, password(可选重置)
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}

    with session_scope() as session:
        user: Optional[User] = session.get(User, user_id)
        if not user:
            return jsonify({"error": "not_found", "message": "user not found"}), 404

        if "email" in payload:
            user.email = payload.get("email")
        if "display_name" in payload:
            user.display_name = payload.get("display_name")
        if "is_active" in payload:
            user.is_active = bool(payload.get("is_active"))

        # 重置密码（如果提供）
        new_password = payload.get("password")
        if new_password:
            user.password_hash = generate_password_hash(new_password)

        # 更新角色（如果提供）
        if "roles" in payload:
            role_names: List[str] = payload.get("roles") or []
            if role_names:
                roles = session.query(Role).filter(Role.name.in_(role_names)).all()
                user.roles = roles
            else:
                user.roles = []

        session.flush()
        
        record_audit_log(
            action="USER_UPDATE",
            resource="user",
            resource_id=str(user.id),
            payload=payload,
            status="success"
        )
        
        return jsonify({"user": _user_to_dict(user)})


@bp.delete("/<int:user_id>")
@require_permissions("user:manage")
def delete_user(user_id: int):
    """
    删除用户。

    DELETE /api/users/{id}
    """
    with session_scope() as session:
        user: Optional[User] = session.get(User, user_id)
        if not user:
            return jsonify({"error": "not_found", "message": "user not found"}), 404

        username = user.username
        session.delete(user)
        
        record_audit_log(
            action="USER_DELETE",
            resource="user",
            resource_id=str(user_id),
            payload={"username": username},
            status="success"
        )
        
        return jsonify({"status": "success"})


__all__ = ["bp"]


