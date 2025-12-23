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


def _call_controller(func, *args, **kwargs) -> Any:
    """调用控制层 API，失败时抛出异常。"""
    client = get_controller_client()
    return func(client, *args, **kwargs)


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

    result = _call_controller(lambda c: c.get_honeypot_logs(start_time, end_time))
    return jsonify({"logs": result})
