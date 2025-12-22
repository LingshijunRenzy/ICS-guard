"""
AI 模型推理服务。

按照 docs/model-training-guide.md 和 docs/flow-feature-mapping.md 实现：
- 模型加载（LightGBM 为主）
- 特征向量构建
- 在线推理与决策
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 决策等级
# ---------------------------------------------------------------------------


class DecisionLevel(str, Enum):
    """决策等级，对应不同的策略动作。"""

    NORMAL = "normal"
    ALERT = "alert"
    THROTTLE = "throttle"
    BLOCK = "block"
    REDIRECT = "redirect"


# ---------------------------------------------------------------------------
# 推理结果
# ---------------------------------------------------------------------------


@dataclass
class PredictionResult:
    """推理结果。"""

    prob: float  # 异常概率
    label: str  # 预测标签（Normal / 攻击类型）
    anomaly_score: float  # 异常分数（与 prob 相同或经过变换）
    decision_level: DecisionLevel  # 决策等级

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prob": self.prob,
            "label": self.label,
            "anomaly_score": self.anomaly_score,
            "decision_level": self.decision_level.value,
        }


# ---------------------------------------------------------------------------
# 阈值配置
# ---------------------------------------------------------------------------


@dataclass
class ThresholdConfig:
    """阈值配置。"""

    alert: float = 0.3
    throttle: float = 0.6
    block: float = 0.8
    redirect: float = 0.9

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "ThresholdConfig":
        return cls(
            alert=d.get("alert", 0.3),
            throttle=d.get("throttle", 0.6),
            block=d.get("block", 0.8),
            redirect=d.get("redirect", 0.9),
        )

    def get_decision_level(self, prob: float) -> DecisionLevel:
        """根据概率值返回决策等级。"""
        if prob >= self.redirect:
            return DecisionLevel.REDIRECT
        elif prob >= self.block:
            return DecisionLevel.BLOCK
        elif prob >= self.throttle:
            return DecisionLevel.THROTTLE
        elif prob >= self.alert:
            return DecisionLevel.ALERT
        else:
            return DecisionLevel.NORMAL


# ---------------------------------------------------------------------------
# 特征配置
# ---------------------------------------------------------------------------


@dataclass
class FeatureConfig:
    """特征配置。"""

    # 模型使用的特征列名列表（顺序必须与训练时一致）
    feature_columns: List[str]
    # 标签映射（可选，用于多分类）
    label_mapping: Dict[int, str]
    # 缺失值填充策略
    fill_values: Dict[str, float]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FeatureConfig":
        return cls(
            feature_columns=d.get("feature_columns", []),
            label_mapping=d.get("label_mapping", {0: "Normal", 1: "Attack"}),
            fill_values=d.get("fill_values", {}),
        )

    @classmethod
    def default(cls) -> "FeatureConfig":
        """默认特征配置（基于 flow-feature-mapping.md）。"""
        return cls(
            feature_columns=[
                "duration",
                "pkt_count",
                "byte_count",
                "pkt_rate",
                "byte_rate",
            ],
            label_mapping={0: "Normal", 1: "Attack"},
            fill_values={
                "duration": 0.0,
                "pkt_count": 0.0,
                "byte_count": 0.0,
                "pkt_rate": 0.0,
                "byte_rate": 0.0,
            },
        )


# ---------------------------------------------------------------------------
# 推理服务
# ---------------------------------------------------------------------------


class InferenceService:
    """
    AI 推理服务。

    负责：
    - 加载模型和配置
    - 构建特征向量
    - 执行推理并返回决策
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        features_path: Optional[str] = None,
        thresholds_path: Optional[str] = None,
    ) -> None:
        self._model: Any = None
        self._feature_config: FeatureConfig = FeatureConfig.default()
        self._threshold_config: ThresholdConfig = ThresholdConfig()
        self._model_path = model_path
        self._features_path = features_path
        self._thresholds_path = thresholds_path
        self._loaded = False
        self._lock = threading.Lock()

    def load(
        self,
        model_path: Optional[str] = None,
        features_path: Optional[str] = None,
        thresholds_path: Optional[str] = None,
    ) -> bool:
        """
        加载模型和配置。

        返回 True 表示加载成功，False 表示加载失败（可继续使用默认配置）。
        """
        model_path = model_path or self._model_path
        features_path = features_path or self._features_path
        thresholds_path = thresholds_path or self._thresholds_path

        with self._lock:
            success = True

            # 加载模型
            if model_path and os.path.exists(model_path):
                try:
                    with open(model_path, "rb") as f:
                        self._model = pickle.load(f)
                    logger.info("Model loaded from %s", model_path)
                except Exception as e:
                    logger.error("Failed to load model: %s", e)
                    success = False
            else:
                logger.warning("Model file not found: %s", model_path)
                success = False

            # 加载特征配置
            if features_path and os.path.exists(features_path):
                try:
                    with open(features_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._feature_config = FeatureConfig.from_dict(data)
                    logger.info("Feature config loaded from %s", features_path)
                except Exception as e:
                    logger.error("Failed to load feature config: %s", e)
            else:
                logger.info("Using default feature config")

            # 加载阈值配置
            if thresholds_path and os.path.exists(thresholds_path):
                try:
                    with open(thresholds_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._threshold_config = ThresholdConfig.from_dict(data)
                    logger.info("Threshold config loaded from %s", thresholds_path)
                except Exception as e:
                    logger.error("Failed to load threshold config: %s", e)
            else:
                logger.info("Using default threshold config")

            self._loaded = success
            return success

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载。"""
        return self._loaded and self._model is not None

    @property
    def feature_columns(self) -> List[str]:
        """获取特征列名列表。"""
        return self._feature_config.feature_columns

    @property
    def thresholds(self) -> ThresholdConfig:
        """获取阈值配置。"""
        return self._threshold_config

    def build_feature_vector(self, flow: Dict[str, Any]) -> np.ndarray:
        """
        从 Flow 字典构建特征向量。

        按照 flow-feature-mapping.md 的约定：
        - 使用 duration, pkt_count, byte_count, pkt_rate, byte_rate 等字段
        - 对缺失值使用配置的填充策略
        """
        features = []
        for col in self._feature_config.feature_columns:
            val = flow.get(col)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                val = self._feature_config.fill_values.get(col, 0.0)
            features.append(float(val))
        return np.array(features).reshape(1, -1)

    def predict_flow(self, flow: Dict[str, Any]) -> PredictionResult:
        """
        对单个 Flow 进行推理。

        参数：
            flow: Flow 数据字典，包含 API 定义的字段

        返回：
            PredictionResult 包含概率、标签、异常分数和决策等级
        """
        if not self.is_loaded:
            # 模型未加载，返回默认结果
            return PredictionResult(
                prob=0.0,
                label="Unknown",
                anomaly_score=0.0,
                decision_level=DecisionLevel.NORMAL,
            )

        # 构建特征向量
        X = self.build_feature_vector(flow)

        # 执行推理
        try:
            # LightGBM 模型使用 predict_proba
            if hasattr(self._model, "predict_proba"):
                proba = self._model.predict_proba(X)
                # 二分类：取正类（Attack）的概率
                prob = float(proba[0, 1]) if proba.shape[1] > 1 else float(proba[0, 0])
            else:
                # 直接输出概率的模型
                prob = float(self._model.predict(X)[0])

            # 预测标签
            if hasattr(self._model, "predict"):
                pred_class = int(self._model.predict(X)[0])
                label = self._feature_config.label_mapping.get(pred_class, str(pred_class))
            else:
                label = "Attack" if prob >= 0.5 else "Normal"

        except Exception as e:
            logger.error("Prediction failed: %s", e)
            return PredictionResult(
                prob=0.0,
                label="Error",
                anomaly_score=0.0,
                decision_level=DecisionLevel.NORMAL,
            )

        # 计算异常分数和决策等级
        anomaly_score = prob
        decision_level = self._threshold_config.get_decision_level(prob)

        return PredictionResult(
            prob=prob,
            label=label,
            anomaly_score=anomaly_score,
            decision_level=decision_level,
        )

    def predict_batch(self, flows: List[Dict[str, Any]]) -> List[PredictionResult]:
        """批量推理。"""
        return [self.predict_flow(flow) for flow in flows]

    def get_model_meta(self) -> Dict[str, Any]:
        """获取模型元信息。"""
        return {
            "loaded": self.is_loaded,
            "feature_columns": self._feature_config.feature_columns,
            "label_mapping": self._feature_config.label_mapping,
            "thresholds": {
                "alert": self._threshold_config.alert,
                "throttle": self._threshold_config.throttle,
                "block": self._threshold_config.block,
                "redirect": self._threshold_config.redirect,
            },
        }


# ---------------------------------------------------------------------------
# 全局服务实例
# ---------------------------------------------------------------------------

_service_instance: Optional[InferenceService] = None
_service_lock = threading.Lock()


def get_inference_service() -> InferenceService:
    """获取全局推理服务单例（懒加载）。"""
    global _service_instance
    with _service_lock:
        if _service_instance is None:
            _service_instance = InferenceService()
        return _service_instance


def init_inference_service(
    model_path: Optional[str] = None,
    features_path: Optional[str] = None,
    thresholds_path: Optional[str] = None,
) -> InferenceService:
    """初始化并加载推理服务。"""
    service = get_inference_service()
    service.load(model_path, features_path, thresholds_path)
    return service


def reset_inference_service() -> None:
    """重置全局推理服务实例。"""
    global _service_instance
    with _service_lock:
        _service_instance = None
