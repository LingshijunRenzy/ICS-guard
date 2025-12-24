from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from sqlalchemy import desc

from src.app.auth import require_permissions
from src.app.db import session_scope
from src.app.db.models import EventLog
from src.app.services.event_subscriber import EventType, get_recent_events

bp = Blueprint("events", __name__, url_prefix="/api/events")


@bp.get("")
@require_permissions("topology:read", "alert:read")
def list_recent_events():
    """
    返回最近的控制层事件列表，用于前端实时监控页面轮询展示。

    查询参数：
    - limit: 返回条数上限（默认 100，最大 200）
    - types: 可选，逗号分隔的事件类型枚举值，如:
      network_status_update,traffic_anomaly,honeypot_interaction,topology_change,flow_update
    """
    try:
        limit = int(request.args.get("limit", "100"))
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 200))

    type_param = request.args.get("types")
    types: List[EventType] | None = None
    if type_param:
        raw_values = [t.strip() for t in type_param.split(",") if t.strip()]
        mapped: List[EventType] = []
        for v in raw_values:
            try:
                mapped.append(EventType(v))
            except ValueError:
                # 忽略未知类型
                continue
        types = mapped or None

    events = get_recent_events(limit=limit, event_types=set(types) if types is not None else None)
    return jsonify({"items": events})


@bp.get("/logs")
@require_permissions("event_log:read")
def list_event_logs():
    """
    从数据库查询历史自动化事件日志。

    查询参数：
    - page: 页码 (默认 1)
    - per_page: 每页条数 (默认 20)
    - type: 事件类型
    - severity: 严重程度
    - resource: 相关资源 ID
    """
    try:
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "20"))
    except ValueError:
        page, per_page = 1, 20

    event_type = request.args.get("type")
    severity = request.args.get("severity")
    resource = request.args.get("resource")

    with session_scope() as session:
        query = session.query(EventLog)
        if event_type:
            query = query.filter(EventLog.event_type == event_type)
        if severity:
            query = query.filter(EventLog.severity == severity)
        if resource:
            query = query.filter(EventLog.related_resource == resource)
        
        total = query.count()
        items = query.order_by(desc(EventLog.created_at)).offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            "total": total,
            "page": page,
            "per_page": per_page,
            "items": [
                {
                    "id": item.id,
                    "type": item.event_type,
                    "source": item.source,
                    "severity": item.severity,
                    "payload": item.payload_snapshot,
                    "resource": item.related_resource,
                    "processed_by": item.processed_by,
                    "timestamp": item.created_at.isoformat()
                } for item in items
            ]
        })


