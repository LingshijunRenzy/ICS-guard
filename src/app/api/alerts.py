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


def _demo_timestamp() -> str:
    """生成当前 UTC 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


def _try_controller_call(func, *args, **kwargs) -> Any:
    """尝试调用控制层，失败时返回 None。"""
    try:
        client = get_controller_client()
        return func(client, *args, **kwargs)
    except ControllerClientError:
        return None
    except Exception:
        return None


def _demo_alerts() -> List[AlertItem]:
    """演示用告警数据。"""
    return [
        {
            "id": "alert-001",
            "timestamp": "2025-01-01T12:00:00Z",
            "type": "traffic_anomaly",
            "severity": "high",
            "source_ip": "10.0.0.99",
            "description": "High entropy Modbus traffic detected",
        },
        {
            "id": "alert-002",
            "timestamp": "2025-01-01T12:05:00Z",
            "type": "honeypot_interaction",
            "severity": "medium",
            "source_ip": "10.0.0.88",
            "description": "Suspicious write attempt to honeypot",
        },
        {
            "id": "alert-003",
            "timestamp": "2025-01-01T12:10:00Z",
            "type": "connection_anomaly",
            "severity": "low",
            "source_ip": "10.0.0.77",
            "description": "Unusual connection pattern detected",
        },
    ]


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

    result = _try_controller_call(lambda c: c.get_alerts(start_time, end_time, severity))
    if result is not None:
        return jsonify({"alerts": result})

    # 降级到演示数据
    alerts = _demo_alerts()
    # 应用过滤
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity]
    return jsonify({"alerts": alerts})
