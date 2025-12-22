from flask import Flask


def register_routes(app: Flask) -> None:
    """
    注册应用层对外 HTTP 路由。

    目前只提供健康检查接口，其他业务接口按开发计划逐步补齐。
    """
    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}



