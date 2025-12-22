"""
ICS-Guard 应用层 Flask 应用。
"""

import logging
import os
from typing import Optional

from flask import Flask, send_from_directory

logger = logging.getLogger(__name__)


def create_app(static_folder: Optional[str] = None) -> Flask:
    """
    应用层 Flask 工厂。

    初始化流程：
    1. 加载配置
    2. 注册路由
    3. 初始化推理服务（如果模型文件存在）
    4. 挂载前端 SPA 入口（/ui），保持 `/` 仍为 API 首页，避免破坏现有 userspace
    """
    # 默认静态目录指向 src/app/static，用于承载 Vue 构建产物
    if static_folder is None:
        static_folder = os.path.join(os.path.dirname(__file__), "static")

    # static_url_path 设为 /ui，使得 Vite 的 base=/ui/ 下发的静态资源可以被正确服务
    app = Flask(__name__, static_folder=static_folder, static_url_path="/ui")

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

    # 注册前端 SPA 路由
    _register_spa_routes(app)

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


def _register_spa_routes(app: Flask) -> None:
    """
    注册前端 SPA 路由。

    约定：
    - Vue 使用 base=/ui/，构建产物放在 app.static_folder
    - /ui 及其子路径如果存在静态文件则直接返回，否则回退到 index.html 交由前端路由处理
    """

    @app.route("/ui", defaults={"path": ""})
    @app.route("/ui/<path:path>")
    def serve_spa(path: str):
        # 优先返回真实静态文件
        if path:
            candidate = os.path.join(app.static_folder, path)
            if os.path.exists(candidate) and os.path.isfile(candidate):
                return send_from_directory(app.static_folder, path)

        # 兜底返回 index.html
        index_path = os.path.join(app.static_folder, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(app.static_folder, "index.html")

        # 如果前端尚未构建，返回简单提示而不是 404
        return {
            "message": "UI not built yet. Please run `npm run build` in web-ui to generate frontend assets.",
        }

