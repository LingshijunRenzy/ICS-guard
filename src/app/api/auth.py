"""
应用层 Web UI 认证 API。

提供最小登录接口：
- POST /api/auth/login

鉴权逻辑：
- 使用应用层数据库中的 app_users 表
- 使用 Werkzeug 的密码哈希校验
- 返回基于 itsdangerous 签名的访问令牌（Bearer token）
"""

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash

from ..auth import create_access_token
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


__all__ = ["bp"]


