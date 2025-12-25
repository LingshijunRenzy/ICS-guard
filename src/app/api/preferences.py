"""
应用层偏好设置 API。

用于存储和检索用户或全局的 UI 偏好设置，如拓扑图布局、主题设置等。
"""

import json
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request, g

from ..auth import login_required
from ..db import session_scope
from ..db.models import Preference, PreferenceScopeEnum
from ..utils.audit import record_audit_log

bp = Blueprint("preferences", __name__, url_prefix="/api/preferences")


@bp.get("/<key>")
@login_required
def get_preference(key: str):
    """
    获取偏好设置。

    GET /api/preferences/<key>?scope=user|global
    """
    scope = request.args.get("scope", PreferenceScopeEnum.USER)
    
    # 验证 scope
    if scope not in [PreferenceScopeEnum.USER, PreferenceScopeEnum.GLOBAL]:
        return jsonify({"error": "invalid_request", "message": "Invalid scope"}), 400

    user_id = g.current_user_id if scope == PreferenceScopeEnum.USER else None

    with session_scope() as session:
        pref = session.query(Preference).filter_by(
            scope=scope,
            user_id=user_id,
            key=key
        ).first()

        if not pref:
            # 如果找不到用户级配置，尝试查找全局配置作为回退（可选，视需求而定）
            # 这里为了简单，直接返回 404 或 null
            return jsonify({"key": key, "value": None}), 200

        # 尝试解析 JSON
        value = pref.value
        try:
            if value:
                value = json.loads(value)
        except json.JSONDecodeError:
            pass  # 保持原样

        return jsonify({
            "key": pref.key,
            "value": value,
            "scope": pref.scope,
            "updated_at": pref.updated_at.isoformat() if pref.updated_at else None
        })


@bp.put("/<key>")
@login_required
def set_preference(key: str):
    """
    设置偏好设置。

    PUT /api/preferences/<key>
    {
        "value": "...", # JSON object, list, or string
        "scope": "user" # optional, default "user"
    }
    """
    payload = request.get_json(silent=True) or {}
    
    if "value" not in payload:
        return jsonify({"error": "invalid_request", "message": "Missing value"}), 400
        
    value = payload.get("value")
    scope = payload.get("scope", PreferenceScopeEnum.USER)

    # 验证 scope
    if scope not in [PreferenceScopeEnum.USER, PreferenceScopeEnum.GLOBAL]:
        return jsonify({"error": "invalid_request", "message": "Invalid scope"}), 400

    # 权限检查：全局配置通常需要管理员权限
    if scope == PreferenceScopeEnum.GLOBAL:
        # 检查当前用户是否具有 admin 角色
        is_admin = 'admin' in getattr(g, 'current_user_roles', [])
        if not is_admin:
            return jsonify({"error": "forbidden", "message": "Admin access required for global preferences"}), 403

    user_id = g.current_user_id if scope == PreferenceScopeEnum.USER else None

    # 序列化 value
    if isinstance(value, (dict, list, bool, int, float)):
        value_str = json.dumps(value, ensure_ascii=False)
    else:
        value_str = str(value) if value is not None else None

    with session_scope() as session:
        pref = session.query(Preference).filter_by(
            scope=scope,
            user_id=user_id,
            key=key
        ).first()

        if pref:
            pref.value = value_str
        else:
            pref = Preference(
                scope=scope,
                user_id=user_id,
                key=key,
                value=value_str
            )
            session.add(pref)
        
        # 记录审计日志（仅对重要配置或全局配置记录，避免日志爆炸）
        if scope == PreferenceScopeEnum.GLOBAL:
            record_audit_log(
                action="UPDATE_PREFERENCE",
                resource="preference",
                resource_id=key,
                payload={"key": key, "value": value_str},
                status="success"
            )

    return jsonify({
        "status": "success",
        "message": "Preference saved",
        "key": key,
        "scope": scope
    })
