from typing import Any, Dict, List, Optional
from datetime import datetime
import csv
import io
from flask import Blueprint, jsonify, request, Response, make_response
from sqlalchemy import select, desc, and_
from ..auth import require_permissions
from ..db import session_scope
from ..db.models import AuditLog, User, Role

bp = Blueprint("audit", __name__, url_prefix="/api/audit")

@bp.get("")
@require_permissions("audit:read")
def list_audit_logs():
    """
    获取审计日志列表。
    
    Query Params:
        - start_time: ISO 8601 string
        - end_time: ISO 8601 string
        - user_id: int
        - action: string
        - status: string
        - resource: string
        - page: int (default 1)
        - per_page: int (default 20)
    """
    start_time_str = request.args.get("start_time")
    end_time_str = request.args.get("end_time")
    user_id = request.args.get("user_id", type=int)
    action = request.args.get("action")
    status = request.args.get("status")
    resource = request.args.get("resource")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    filters = []
    if start_time_str:
        filters.append(AuditLog.created_at >= datetime.fromisoformat(start_time_str))
    if end_time_str:
        filters.append(AuditLog.created_at <= datetime.fromisoformat(end_time_str))
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action)
    if status:
        filters.append(AuditLog.status == status)
    if resource:
        filters.append(AuditLog.resource == resource)

    with session_scope() as session:
        query = session.query(AuditLog).filter(*filters).order_by(desc(AuditLog.created_at))
        
        total = query.count()
        logs = query.offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            "total": total,
            "page": page,
            "per_page": per_page,
            "logs": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "username": log.username,
                    "action": log.action,
                    "resource": log.resource,
                    "resource_id": log.resource_id,
                    "payload_snapshot": log.payload_snapshot,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "status": log.status,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat() if log.created_at else None
                }
                for log in logs
            ]
        })

@bp.get("/export")
@require_permissions("audit:read")
def export_audit_logs():
    """
    导出审计日志为 CSV。
    支持与列表相同的过滤条件。
    """
    start_time_str = request.args.get("start_time")
    end_time_str = request.args.get("end_time")
    user_id = request.args.get("user_id", type=int)
    action = request.args.get("action")
    status = request.args.get("status")
    resource = request.args.get("resource")

    filters = []
    if start_time_str:
        filters.append(AuditLog.created_at >= datetime.fromisoformat(start_time_str))
    if end_time_str:
        filters.append(AuditLog.created_at <= datetime.fromisoformat(end_time_str))
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action)
    if status:
        filters.append(AuditLog.status == status)
    if resource:
        filters.append(AuditLog.resource == resource)

    with session_scope() as session:
        logs = session.query(AuditLog).filter(*filters).order_by(desc(AuditLog.created_at)).all()

        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        writer.writerow([
            "ID", "Time", "User", "Action", "Resource", "Resource ID", 
            "IP Address", "Status", "Error Message", "Payload Snapshot"
        ])
        
        for log in logs:
            writer.writerow([
                log.id,
                log.created_at.isoformat() if log.created_at else "",
                log.username or f"ID:{log.user_id}" if log.user_id else "System",
                log.action,
                log.resource or "",
                log.resource_id or "",
                log.ip_address or "",
                log.status,
                log.error_message or "",
                log.payload_snapshot or ""
            ])

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        response.headers["Content-type"] = "text/csv"
        return response

@bp.get("/actions")
@require_permissions("audit:read")
def get_audit_actions():
    """获取所有已记录的动作类型，用于前端过滤下拉框。"""
    with session_scope() as session:
        actions = session.query(AuditLog.action).distinct().all()
        return jsonify({"actions": [a[0] for a in actions]})
