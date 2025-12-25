"""
应用层配置模块。

所有敏感配置通过环境变量注入，避免硬编码。
"""

import os
from typing import Any, Dict

from flask import Flask


# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    # 环境标识
    "ENV": "development",
    "DEBUG": False,
    # JSON 配置：允许中文直接显示
    "JSON_AS_ASCII": False,
    # 控制层连接
    "CONTROLLER_BASE_URL": "http://localhost:8080",
    "CONTROLLER_CLIENT_ID": "app-layer-client",
    "CONTROLLER_CLIENT_SECRET": "app-layer-secret",
    "CONTROLLER_WS_BASE_URL": "ws://localhost:8080",
    # 是否启用控制层 WebSocket 订阅（默认开启，可通过环境变量关闭）
    "ENABLE_CONTROLLER_WS": True,
    # UI WebSocket 服务端配置（用于 /ws/ui-events）
    "UI_WS_HOST": "0.0.0.0",
    "UI_WS_PORT": 8766,
    # 模型与推理（默认指向最新一次训练输出，可通过环境变量覆盖）
    "MODEL_DIR": "models",
    "MODEL_FILE": "251225_105021_lightgbm_model.pkl",
    "FEATURES_FILE": "251225_105021_features.json",
    "THRESHOLDS_FILE": "251225_105021_thresholds.json",
    # 推理阈值（默认值，可被配置文件覆盖）
    "THRESHOLD_ALERT": 0.3,
    "THRESHOLD_THROTTLE": 0.6,
    "THRESHOLD_BLOCK": 0.8,
    "THRESHOLD_REDIRECT": 0.9,
    # Flask 核心配置
    "SECRET_KEY": "ics-guard-dev-secret",
}


# ---------------------------------------------------------------------------
# 环境变量映射
# ---------------------------------------------------------------------------

ENV_MAPPING: Dict[str, str] = {
    "ICS_GUARD_ENV": "ENV",
    "ICS_GUARD_DEBUG": "DEBUG",
    "ICS_GUARD_CONTROLLER_URL": "CONTROLLER_BASE_URL",
    "ICS_GUARD_CONTROLLER_CLIENT_ID": "CONTROLLER_CLIENT_ID",
    "ICS_GUARD_CONTROLLER_CLIENT_SECRET": "CONTROLLER_CLIENT_SECRET",
    "ICS_GUARD_CONTROLLER_WS_URL": "CONTROLLER_WS_BASE_URL",
    "ICS_GUARD_ENABLE_CONTROLLER_WS": "ENABLE_CONTROLLER_WS",
    "ICS_GUARD_UI_WS_HOST": "UI_WS_HOST",
    "ICS_GUARD_UI_WS_PORT": "UI_WS_PORT",
    "ICS_GUARD_MODEL_DIR": "MODEL_DIR",
    "ICS_GUARD_MODEL_FILE": "MODEL_FILE",
    "ICS_GUARD_FEATURES_FILE": "FEATURES_FILE",
    "ICS_GUARD_THRESHOLDS_FILE": "THRESHOLDS_FILE",
    "ICS_GUARD_THRESHOLD_ALERT": "THRESHOLD_ALERT",
    "ICS_GUARD_THRESHOLD_THROTTLE": "THRESHOLD_THROTTLE",
    "ICS_GUARD_THRESHOLD_BLOCK": "THRESHOLD_BLOCK",
    "ICS_GUARD_THRESHOLD_REDIRECT": "THRESHOLD_REDIRECT",
}


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------


def load_config(app: Flask) -> None:
    """
    加载配置到 Flask app。

    优先级：环境变量 > 默认值
    """
    config: Dict[str, Any] = dict(DEFAULT_CONFIG)

    for env_key, config_key in ENV_MAPPING.items():
        env_val = os.getenv(env_key)
        if env_val is not None:
            # 类型转换
            default_val = DEFAULT_CONFIG.get(config_key)
            if isinstance(default_val, bool):
                config[config_key] = env_val.lower() in ("true", "1", "yes")
            elif isinstance(default_val, float):
                config[config_key] = float(env_val)
            elif isinstance(default_val, int):
                config[config_key] = int(env_val)
            else:
                config[config_key] = env_val

    app.config.update(config)


def get_model_path(app: Flask) -> str:
    """获取模型文件完整路径。"""
    return os.path.join(app.config["MODEL_DIR"], app.config["MODEL_FILE"])


def get_features_path(app: Flask) -> str:
    """获取特征配置文件完整路径。"""
    return os.path.join(app.config["MODEL_DIR"], app.config["FEATURES_FILE"])


def get_thresholds_path(app: Flask) -> str:
    """获取阈值配置文件完整路径。"""
    return os.path.join(app.config["MODEL_DIR"], app.config["THRESHOLDS_FILE"])
