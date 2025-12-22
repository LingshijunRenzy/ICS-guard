"""
ICS-Guard 应用层 Flask 应用。
"""

import logging
from flask import Flask

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """
    应用层 Flask 工厂。

    初始化流程：
    1. 加载配置
    2. 注册路由
    3. 初始化推理服务（如果模型文件存在）
    """
    app = Flask(__name__)

    # 延迟导入以避免循环依赖
    from .config import load_config, get_model_path, get_features_path, get_thresholds_path
    from .api import register_routes

    # 加载配置
    load_config(app)

    # 注册路由
    register_routes(app)

    # 初始化推理服务
    with app.app_context():
        _init_inference_service(app)

    logger.info("ICS-Guard application initialized")
    return app


def _init_inference_service(app: Flask) -> None:
    """初始化推理服务（如果模型文件存在）。"""
    from .config import get_model_path, get_features_path, get_thresholds_path
    from .services.inference import init_inference_service

    model_path = get_model_path(app)
    features_path = get_features_path(app)
    thresholds_path = get_thresholds_path(app)

    try:
        service = init_inference_service(model_path, features_path, thresholds_path)
        if service.is_loaded:
            logger.info("Inference service initialized with model: %s", model_path)
        else:
            logger.warning("Inference service initialized without model (demo mode)")
    except Exception as e:
        logger.warning("Failed to initialize inference service: %s", e)
