"""
模型与检测 API 路由。

严格按照 docs/api/README.md 和 docs/model-training-guide.md 定义的数据结构。
"""

from typing import Any, Dict

from flask import Blueprint, jsonify, request

from .schemas import FlowInfo
from ..auth import require_permissions
from ..services.inference import get_inference_service

bp = Blueprint("model", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@bp.post("/detect/flow")
@require_permissions("model:detect")
def detect_flow():
    """
    流级检测接口。

    POST /api/detect/flow

    请求体：Flow 数据结构（参考 docs/api/README.md）
    {
        "id": string (可选),
        "src_ip": string,
        "dst_ip": string,
        "src_port": number (可选),
        "dst_port": number (可选),
        "protocol": string,
        "start_time": string (可选),
        "end_time": string (可选),
        "duration": number,
        "pkt_count": number,
        "byte_count": number,
        "pkt_rate": number,
        "byte_rate": number,
        "func_code_entropy": number (可选),
        "reg_addr_std": number (可选),
        "status": string (可选)
    }

    响应结构：
    {
        "prob": number,           # 异常概率 (0.0 - 1.0)
        "label": string,          # 预测标签 (Normal / Attack 类型)
        "anomaly_score": number,  # 异常分数
        "decision_level": string, # 决策等级 (normal/alert/throttle/block/redirect)
        "flow_id": string         # 输入的 flow id (如有)
    }
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}

    # 获取推理服务
    service = get_inference_service()

    # 执行推理
    result = service.predict_flow(payload)

    return jsonify({
        "prob": result.prob,
        "label": result.label,
        "anomaly_score": result.anomaly_score,
        "decision_level": result.decision_level.value,
        "flow_id": payload.get("id", ""),
    })


@bp.get("/model/meta")
@require_permissions("model:read")
def get_model_meta():
    """
    获取模型元信息。

    GET /api/model/meta

    响应结构：
    {
        "model_type": string,        # 模型类型 (lightgbm)
        "version": string,           # 模型版本
        "loaded": boolean,           # 模型是否已加载
        "feature_columns": [string], # 特征列名列表
        "label_mapping": object,     # 标签映射
        "thresholds": {              # 阈值配置
            "alert": number,
            "throttle": number,
            "block": number,
            "redirect": number
        }
    }
    """
    service = get_inference_service()
    meta = service.get_model_meta()

    return jsonify({
        "model_type": "lightgbm",
        "version": "1.0.0",
        "loaded": meta["loaded"],
        "feature_columns": meta["feature_columns"],
        "label_mapping": meta["label_mapping"],
        "thresholds": meta["thresholds"],
    })


@bp.post("/detect/batch")
@require_permissions("model:detect")
def detect_batch():
    """
    批量流级检测接口。

    POST /api/detect/batch

    请求体：
    {
        "flows": [Flow, ...]
    }

    响应结构：
    {
        "results": [
            {
                "prob": number,
                "label": string,
                "anomaly_score": number,
                "decision_level": string,
                "flow_id": string
            },
            ...
        ]
    }
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    flows = payload.get("flows", [])

    service = get_inference_service()
    results = service.predict_batch(flows)

    return jsonify({
        "results": [
            {
                "prob": r.prob,
                "label": r.label,
                "anomaly_score": r.anomaly_score,
                "decision_level": r.decision_level.value,
                "flow_id": flows[i].get("id", "") if i < len(flows) else "",
            }
            for i, r in enumerate(results)
        ]
    })
