"""
应用层 Web UI 认证 API。

提供最小登录接口：
- POST /api/auth/login

鉴权逻辑：
- 使用应用层数据库中的 app_users 表
- 使用 Werkzeug 的密码哈希校验
- 返回基于 itsdangerous 签名的访问令牌（Bearer token）
"""

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request, g
from werkzeug.security import check_password_hash

from ..auth import create_access_token, get_current_user
from ..db import session_scope
from ..db.models import User

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    """
    用户登录。

    POST /api/auth/login

    请求体：
    {
        "username": "admin",
        "password": "xxx"
    }

    响应：
    {
        "access_token": "xxx",
        "token_type": "bearer",
        "expires_in": 3600
    }
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return (
            jsonify({"error": "invalid_request", "message": "username and password are required"}),
            400,
        )

    with session_scope() as session:
        user = session.query(User).filter_by(username=username).first()

        if not user or not user.is_active:
            return jsonify({"error": "invalid_credentials", "message": "Invalid username or password"}), 401

        if not check_password_hash(user.password_hash, password):
            return jsonify({"error": "invalid_credentials", "message": "Invalid username or password"}), 401

        # 生成访问令牌
        expires_in = 3600
        access_token = create_access_token(user, expires_in=expires_in)

        return jsonify(
            {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": expires_in,
            }
        )


@bp.get("/me")
def me():
    """
    获取当前登录用户的基本信息和权限集合。

    GET /api/auth/me

    响应示例：
    {
        "id": 1,
        "username": "admin",
        "email": "admin@example.com",
        "display_name": "Admin",
        "is_active": true,
        "roles": ["admin"],
        "permissions": ["topology:read", "policy:read", ...]
    }
    """
    user, error = get_current_user()

    if error == "missing_token":
        return (
            jsonify({"error": "unauthorized", "message": "Missing or invalid Authorization header"}),
            401,
        )
    if error in ("invalid_token", "inactive_user") or user is None:
        return jsonify({"error": "forbidden", "message": "Invalid or inactive user"}), 403

    user_perms = getattr(g, "current_user_permissions", None)
    # 权限集合已经在 get_current_user 中基于 ORM 关系计算好，这里只读取缓存的值
    perms: List[str]
    if user_perms is None:
        perms = []
    else:
        perms = sorted(list(user_perms))

    # 为避免 DetachedInstanceError，这里不再直接访问 user ORM 实例，
    # 而是基于当前 user_id 重新开启会话并在会话内部构造纯字典响应。
    user_id = getattr(g, "current_user_id", None)
    if user_id is None:
        return jsonify({"error": "forbidden", "message": "Invalid or inactive user"}), 403

    from ..db import session_scope as _session_scope

    with _session_scope() as session:
        db_user = session.query(User).filter(User.id == user_id).first()
        if not db_user or not db_user.is_active:
            return jsonify({"error": "forbidden", "message": "Invalid or inactive user"}), 403

        data = {
            "id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "display_name": db_user.display_name,
            "is_active": db_user.is_active,
            "roles": [r.name for r in db_user.roles],
            "permissions": perms,
        }

        return jsonify(data)


__all__ = ["bp"]


