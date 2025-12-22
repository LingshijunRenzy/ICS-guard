"""
蜜罐日志 API 路由。

严格按照 docs/api/README.md 定义的数据结构。
"""

from datetime import datetime, timezone
from typing import Any, List, Optional

from flask import Blueprint, jsonify, request

from .schemas import HoneypotLogItem
from ..auth import require_permissions
from ..services.controller_client import (
    ControllerClientError,
    get_controller_client,
)

bp = Blueprint("honeypot", __name__, url_prefix="/api/honeypot")


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


def _demo_honeypot_logs() -> List[HoneypotLogItem]:
    """演示用蜜罐日志数据。"""
    return [
        {
            "id": "hp-log-001",
            "timestamp": "2025-01-01T12:00:00Z",
            "source_ip": "10.0.0.99",
            "request": "WRITE_SINGLE_REGISTER addr=40001 value=9999",
            "response": "OK",
        },
        {
            "id": "hp-log-002",
            "timestamp": "2025-01-01T12:01:00Z",
            "source_ip": "10.0.0.99",
            "request": "READ_HOLDING_REGISTERS addr=40001 count=10",
            "response": "DATA: [9999, 0, 0, 0, 0, 0, 0, 0, 0, 0]",
        },
        {
            "id": "hp-log-003",
            "timestamp": "2025-01-01T12:05:00Z",
            "source_ip": "10.0.0.88",
            "request": "WRITE_MULTIPLE_REGISTERS addr=40001 values=[1,2,3,4,5]",
            "response": "OK",
        },
    ]


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@bp.get("/logs")
@require_permissions("honeypot:read")
def get_honeypot_logs():
    """
    获取蜜罐日志。

    GET /api/honeypot/logs
    Query params:
        - start_time: string (可选) ISO 8601 格式开始时间
        - end_time: string (可选) ISO 8601 格式结束时间

    响应结构：
    {
        "logs": [
            {
                "id": string,
                "timestamp": string (ISO 8601),
                "source_ip": string,
                "request": string,
                "response": string
            },
            ...
        ]
    }
    """
    start_time: Optional[str] = request.args.get("start_time")
    end_time: Optional[str] = request.args.get("end_time")

    result = _try_controller_call(lambda c: c.get_honeypot_logs(start_time, end_time))
    if result is not None:
        return jsonify({"logs": result})

    # 降级到演示数据
    return jsonify({"logs": _demo_honeypot_logs()})
