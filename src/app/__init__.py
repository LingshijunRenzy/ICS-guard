from flask import Flask


def create_app() -> Flask:
    """
    应用层 Flask 工厂。

    仅做最小初始化：加载配置、注册基础蓝图/路由。
    具体业务模块在后续迭代中填充。
    """
    app = Flask(__name__)

    # 延迟导入以避免循环依赖
    from .config import load_config
    from .api import register_routes

    load_config(app)
    register_routes(app)

    return app



