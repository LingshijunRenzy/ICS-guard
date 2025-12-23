"""
告警 API 路由。

严格按照 docs/api/README.md 定义的数据结构。
"""

from datetime import datetime, timezone
from typing import Any, List, Optional

from flask import Blueprint, jsonify, request

from .schemas import AlertItem
from ..auth import require_permissions
from ..services.controller_client import (
    ControllerClientError,
    get_controller_client,
)

bp = Blueprint("alerts", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _call_controller(func, *args, **kwargs) -> Any:
    """调用控制层 API，失败时抛出异常。"""
    client = get_controller_client()
    return func(client, *args, **kwargs)


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@bp.get("/alerts")
@require_permissions("alert:read")
def get_alerts():
    """
    获取安全告警列表。

    GET /api/alerts
    Query params:
        - start_time: string (可选) ISO 8601 格式开始时间
        - end_time: string (可选) ISO 8601 格式结束时间
        - severity: string (可选) 告警级别 (low, medium, high)

    响应结构：
    {
        "alerts": [
            {
                "id": string,
                "timestamp": string (ISO 8601),
                "type": string,
                "severity": string,
                "source_ip": string,
                "description": string
            },
            ...
        ]
    }
    """
    start_time: Optional[str] = request.args.get("start_time")
    end_time: Optional[str] = request.args.get("end_time")
    severity: Optional[str] = request.args.get("severity")

    result = _call_controller(lambda c: c.get_alerts(start_time, end_time, severity))
    return jsonify({"alerts": result})
