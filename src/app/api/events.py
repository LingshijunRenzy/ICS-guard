from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from src.app.auth import require_permissions
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


