from flask import Flask, jsonify

from . import alerts, auth, events, honeypot, model, policies, roles, topology, users
from ..services.controller_client import (
    AuthenticationError,
    ControllerClientError,
    TokenExpiredError,
)


def register_routes(app: Flask) -> None:
    """
    注册应用层对外 HTTP 路由。

    当前按开发计划提供：
    - 首页与健康检查
    - 拓扑与状态相关 API
    - 策略管理相关 API
    - 告警与蜜罐日志
    - 模型与检测
    """

    @app.get("/")
    def index():
        """API 首页，返回可用端点列表。"""
        return jsonify({
            "name": "ICS-Guard API",
            "version": "1.0.0",
            "description": "基于SDN的工业控制网络智能流量监测与动态隔离系统",
            "endpoints": {
                "健康检查": "GET /healthz",
                "拓扑": {
                    "获取拓扑": "GET /api/topology",
                    "节点状态": "GET /api/nodes/{id}/status",
                    "连接状态": "GET /api/links/{id}/status",
                    "节点统计": "GET /api/nodes/stats",
                    "连接统计": "GET /api/links/stats",
                },
                "策略管理": {
                    "列表": "GET /api/policies",
                    "详情": "GET /api/policies/{id}",
                    "创建": "POST /api/policies",
                    "更新": "PUT /api/policies/{id}",
                    "删除": "DELETE /api/policies/{id}",
                    "应用": "POST /api/policies/{id}/apply",
                    "撤销": "POST /api/policies/{id}/revoke",
                },
                "告警": "GET /api/alerts",
                "蜜罐日志": "GET /api/honeypot/logs",
                "模型检测": {
                    "单流检测": "POST /api/detect/flow",
                    "批量检测": "POST /api/detect/batch",
                    "模型信息": "GET /api/model/meta",
                },
            },
        })

    @app.get("/healthz")
    def healthz():
        """健康检查接口。"""
        return jsonify({"status": "ok"})

    # 注册错误处理器
    @app.errorhandler(AuthenticationError)
    @app.errorhandler(TokenExpiredError)
    def handle_auth_error(e):
        """处理认证错误。"""
        return jsonify({
            "error": "authentication_failed",
            "message": str(e),
        }), 401

    @app.errorhandler(ControllerClientError)
    def handle_controller_error(e):
        """处理控制层客户端错误。"""
        return jsonify({
            "error": "controller_error",
            "message": str(e),
        }), 502  # Bad Gateway，表示无法连接到控制层或控制层返回错误

    # 业务 API 蓝图
    app.register_blueprint(auth.bp)
    app.register_blueprint(topology.bp)
    app.register_blueprint(policies.bp)
    app.register_blueprint(alerts.bp)
    app.register_blueprint(honeypot.bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(model.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(roles.bp)
