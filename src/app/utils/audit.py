from typing import Any, Optional, Dict
from flask import request, g
from ..db import session_scope
from ..db.models import AuditLog, User
import json

def record_audit_log(
    action: str,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None
):
    """
    记录审计日志。
    
    Args:
        action: 动作类型 (如 'LOGIN', 'POLICY_CREATE')
        resource: 资源类型 (如 'policy', 'user')
        resource_id: 资源 ID
        payload: 详细信息的字典 (将存入 payload_snapshot)
        user_id: 用户 ID
        username: 用户名 (冗余存储，防止用户删除后无法追溯)
        status: 状态 ('success' 或 'failure')
        error_message: 失败时的错误信息
    """
    # 如果没有提供 user_id/username，尝试从 flask.g 中获取
    if user_id is None and hasattr(g, 'user') and g.user:
        user_id = g.user.id
        if username is None:
            username = g.user.username
    
    # 获取客户端信息
    ip_address = request.remote_addr if request else None
    user_agent = request.user_agent.string if request and request.user_agent else None
    
    payload_snapshot = json.dumps(payload, ensure_ascii=False) if payload else None
    
    try:
        with session_scope() as session:
            log = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                resource=resource,
                resource_id=resource_id,
                payload_snapshot=payload_snapshot,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                error_message=error_message
            )
            session.add(log)
    except Exception as e:
        print(f"Failed to record audit log: {e}")
