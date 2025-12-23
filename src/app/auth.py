"""
应用层认证与 RBAC 权限检查。

提供：
- 访问令牌生成与验证（基于 itsdangerous）
- 当前用户解析
- require_permissions 装饰器，用于保护敏感 API
"""

from functools import wraps
from typing import Optional, Tuple, Set

from flask import current_app, jsonify, request, g
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import joinedload

from .db import session_scope
from .db.models import User, Role, Permission


# ---------------------------------------------------------------------------
# Token 相关
# ---------------------------------------------------------------------------


def _get_serializer() -> URLSafeTimedSerializer:
    """
    基于 Flask SECRET_KEY 创建签名序列化器。

    使用 itsdangerous 生成类似 JWT 的带过期时间的 token。
    """
    secret_key = current_app.config.get("SECRET_KEY") or "ics-guard-dev-secret"
    return URLSafeTimedSerializer(secret_key, salt="ics-guard-auth")


def create_access_token(user: User, expires_in: int = 3600) -> str:
    """
    为指定用户生成访问令牌。

    Payload:
        - sub: 用户 ID
        - username: 用户名
    过期时间由 expires_in 控制（秒）。
    """
    s = _get_serializer()
    payload = {
        "sub": user.id,
        "username": user.username,
    }
    # itsdangerous 不直接存储过期时间，而是在 loads 时传入 max_age
    return s.dumps(payload)


def _decode_token(token: str, max_age: Optional[int] = None) -> Optional[dict]:
    """解码并验证 token，失败返回 None。"""
    s = _get_serializer()
    try:
        data = s.loads(token, max_age=max_age)
        return data
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(max_age: Optional[int] = 3600) -> Tuple[Optional[User], Optional[str]]:
    """
    从 Authorization 头中解析当前用户。

    返回 (user, error)，其中：
        - user: 成功解析到的 User 实例或 None（注意：会话结束后该实例处于 detached 状态，只能用于身份标识，不应用于访问数据库字段）
        - error: 出错时的错误代码字符串（"missing_token"/"invalid_token"/"inactive_user"）
    """
    # 如果之前已经解析过，直接复用
    if hasattr(g, "current_user"):
        return g.current_user, None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, "missing_token"

    token = auth_header[len("Bearer ") :].strip()
    if not token:
        return None, "missing_token"

    data = _decode_token(token, max_age=max_age)
    if not data or "sub" not in data:
        return None, "invalid_token"

    user_id = data["sub"]

    with session_scope() as session:
        # 预加载 roles 和 permissions，避免会话关闭后再 lazy load 导致 DetachedInstanceError
        user: Optional[User] = (
            session.query(User)
            .options(joinedload(User.roles).joinedload(Role.permissions))
            .filter(User.id == user_id)
            .first()
        )

        if not user or not user.is_active:
            return None, "inactive_user"

        # 计算权限集合并缓存到 g 上，避免后续再访问 ORM 关系
        perms: Set[str] = set()
        for role in user.roles:
            for perm in role.permissions:
                perms.add(perm.code)

        # 只在 g 上缓存“值类型”信息，避免后续在会话之外访问 ORM 属性导致 DetachedInstanceError
        g.current_user_id = user.id
        g.current_user_username = user.username
        g.current_user_permissions = perms

        # 返回的 user 仅用于向后兼容旧代码的身份检查场景
        g.current_user = user
        return user, None


# ---------------------------------------------------------------------------
# 权限检查装饰器
# ---------------------------------------------------------------------------


def require_permissions(*required_permissions: str):
    """
    权限检查装饰器。

    使用示例：
        @bp.post(\"/nodes/<string:node_id>/start\")
        @require_permissions(\"node:control\")
        def start_node(node_id: str):
            ...

    行为：
        - 无 token 或 token 非法 → 401
        - 用户存在但未激活 → 403
        - 用户无任一所需权限 → 403
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user, error = get_current_user()

            if error == "missing_token":
                return (
                    jsonify({"error": "unauthorized", "message": "Missing or invalid Authorization header"}),
                    401,
                )
            if error in ("invalid_token", "inactive_user") or user is None:
                return jsonify({"error": "forbidden", "message": "Invalid or inactive user"}), 403

            # 权限检查：目前要求用户至少拥有其中一个权限
            user_perms = getattr(g, "current_user_permissions", None)
            if user_perms is None:
                # 兼容性兜底：从用户对象重新计算
                user_perms = user.get_all_permissions()
            if not any(p in user_perms for p in required_permissions):
                return (
                    jsonify(
                        {
                            "error": "forbidden",
                            "message": "Insufficient permissions",
                            "required": list(required_permissions),
                        }
                    ),
                    403,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "create_access_token",
    "get_current_user",
    "require_permissions",
]


