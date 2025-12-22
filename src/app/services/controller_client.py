"""
控制层 REST 客户端。

严格按照 docs/api/README.md 定义实现与 SDN 控制层的通信。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from flask import current_app


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class TokenPair:
    """访问令牌与刷新令牌对。"""

    access_token: str
    refresh_token: str
    expires_at: float = field(default=0.0)  # UNIX 时间戳


@dataclass
class NodeStatus:
    """节点状态。"""

    node_id: str
    status: str
    last_updated: str
    metrics: Dict[str, Any]


@dataclass
class LinkStatus:
    """连接状态。"""

    link_id: str
    status: str
    last_updated: str
    metrics: Dict[str, Any]


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class ControllerClientError(Exception):
    """控制层客户端通用异常。"""


class AuthenticationError(ControllerClientError):
    """认证失败。"""


class TokenExpiredError(AuthenticationError):
    """令牌过期。"""


# ---------------------------------------------------------------------------
# 客户端实现
# ---------------------------------------------------------------------------


class ControllerClient:
    """
    调用 SDN 控制层 REST API 的客户端。

    功能：
    - 封装鉴权（获取/刷新令牌）
    - 封装拓扑、节点、连接、策略、告警、蜜罐日志等接口
    - 自动管理 Token 生命周期，401 时尝试刷新
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        if base_url is None:
            base_url = current_app.config.get("CONTROLLER_BASE_URL", "http://localhost:8000")
        self.base_url = base_url.rstrip("/")
        self._client_id = client_id or current_app.config.get("CONTROLLER_CLIENT_ID", "")
        self._client_secret = client_secret or current_app.config.get("CONTROLLER_CLIENT_SECRET", "")
        self._timeout = timeout

        self._token: Optional[TokenPair] = None
        self._token_lock = threading.Lock()

    # -----------------------------------------------------------------------
    # 鉴权相关
    # -----------------------------------------------------------------------

    def get_token(self, client_id: Optional[str] = None, client_secret: Optional[str] = None) -> TokenPair:
        """
        获取访问令牌。

        POST /auth/token
        """
        cid = client_id or self._client_id
        csec = client_secret or self._client_secret
        resp = requests.post(
            f"{self.base_url}/auth/token",
            json={"client_id": cid, "client_secret": csec},
            timeout=self._timeout,
        )
        self._raise_for_status(resp)
        data = self._extract_data(resp)
        token = TokenPair(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=time.time() + data.get("expires_in", 3600),
        )
        with self._token_lock:
            self._token = token
        return token

    def refresh_token(self, refresh_token: Optional[str] = None) -> TokenPair:
        """
        刷新访问令牌。

        GET /auth/refresh
        """
        rt = refresh_token
        if rt is None:
            with self._token_lock:
                if self._token is None:
                    raise AuthenticationError("No token available to refresh")
                rt = self._token.refresh_token
        resp = requests.get(
            f"{self.base_url}/auth/refresh",
            headers={"Authorization": f"Bearer {rt}"},
            timeout=self._timeout,
        )
        self._raise_for_status(resp)
        data = self._extract_data(resp)
        token = TokenPair(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=time.time() + data.get("expires_in", 3600),
        )
        with self._token_lock:
            self._token = token
        return token

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        验证令牌有效性。

        POST /auth/verify
        """
        resp = requests.post(
            f"{self.base_url}/auth/verify",
            json={"token": token},
            timeout=self._timeout,
        )
        self._raise_for_status(resp)
        return self._extract_data(resp)

    def revoke_token(self, token: str) -> bool:
        """
        撤销令牌。

        POST /auth/revoke
        """
        resp = requests.post(
            f"{self.base_url}/auth/revoke",
            json={"token": token},
            timeout=self._timeout,
        )
        self._raise_for_status(resp)
        data = self._extract_data(resp)
        return data.get("revoked", False)

    def ensure_token(self) -> str:
        """确保有可用的 access_token，必要时自动获取或刷新。"""
        with self._token_lock:
            if self._token is None:
                # 没有 token，需要先获取
                pass
            elif self._token.expires_at > time.time() + 60:
                # token 还有效（提前 60 秒刷新）
                return self._token.access_token
            else:
                # 尝试刷新
                try:
                    self.refresh_token()
                    if self._token:
                        return self._token.access_token
                except Exception:
                    pass
        # 重新获取 token
        self.get_token()
        with self._token_lock:
            if self._token:
                return self._token.access_token
        raise AuthenticationError("Failed to obtain access token")

    # -----------------------------------------------------------------------
    # 通用请求方法
    # -----------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        auth: bool = True,
        retry_on_401: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        统一请求入口。

        - auth=True 时自动附加 Authorization header
        - retry_on_401=True 时遇到 401 自动刷新 token 重试一次
        """
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        if auth:
            headers["Authorization"] = f"Bearer {self.ensure_token()}"
        kwargs["headers"] = headers
        kwargs.setdefault("timeout", self._timeout)

        resp = requests.request(method, url, **kwargs)

        # 401 重试逻辑
        if resp.status_code == 401 and auth and retry_on_401:
            try:
                self.refresh_token()
            except Exception:
                self.get_token()
            headers["Authorization"] = f"Bearer {self.ensure_token()}"
            resp = requests.request(method, url, **kwargs)

        self._raise_for_status(resp)
        return self._extract_data(resp)

    def _raise_for_status(self, resp: requests.Response) -> None:
        """根据响应状态码抛出异常。"""
        if resp.status_code == 401:
            raise AuthenticationError(f"Authentication failed: {resp.text}")
        if resp.status_code >= 400:
            raise ControllerClientError(f"Request failed ({resp.status_code}): {resp.text}")

    def _extract_data(self, resp: requests.Response) -> Dict[str, Any]:
        """从响应体中提取 data 字段（按 API 约定的响应结构）。"""
        try:
            body = resp.json()
        except ValueError:
            return {}
        # 按约定，响应体为 {code, message, metadata, data}
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body

    # -----------------------------------------------------------------------
    # 拓扑管理
    # -----------------------------------------------------------------------

    def get_topology(self) -> Dict[str, Any]:
        """
        获取网络拓扑信息。

        GET /topology
        """
        return self._request("GET", "/topology")

    # -----------------------------------------------------------------------
    # 状态监控
    # -----------------------------------------------------------------------

    def get_node_status(self, node_id: str) -> NodeStatus:
        """
        获取节点状态。

        GET /nodes/{node_id}/status
        """
        data = self._request("GET", f"/nodes/{node_id}/status")
        return NodeStatus(
            node_id=data.get("node_id", node_id),
            status=data.get("status", "unknown"),
            last_updated=data.get("last_updated", ""),
            metrics=data.get("metrics", {}),
        )

    def get_link_status(self, link_id: str) -> LinkStatus:
        """
        获取连接状态。

        GET /links/{link_id}/status
        """
        data = self._request("GET", f"/links/{link_id}/status")
        return LinkStatus(
            link_id=data.get("link_id", link_id),
            status=data.get("status", "unknown"),
            last_updated=data.get("last_updated", ""),
            metrics=data.get("metrics", {}),
        )

    # -----------------------------------------------------------------------
    # 节点操作
    # -----------------------------------------------------------------------

    def start_node(self, node_id: str) -> Dict[str, Any]:
        """
        启动节点。

        POST /nodes/{node_id}/start
        """
        return self._request("POST", f"/nodes/{node_id}/start")

    def stop_node(self, node_id: str) -> Dict[str, Any]:
        """
        停止节点。

        POST /nodes/{node_id}/stop
        """
        return self._request("POST", f"/nodes/{node_id}/stop")

    def restart_node(self, node_id: str) -> Dict[str, Any]:
        """
        重启节点。

        POST /nodes/{node_id}/restart
        """
        return self._request("POST", f"/nodes/{node_id}/restart")

    # -----------------------------------------------------------------------
    # 连接操作
    # -----------------------------------------------------------------------

    def enable_link(self, link_id: str) -> Dict[str, Any]:
        """
        启用连接。

        POST /links/{link_id}/enable
        """
        return self._request("POST", f"/links/{link_id}/enable")

    def disable_link(self, link_id: str) -> Dict[str, Any]:
        """
        禁用连接。

        POST /links/{link_id}/disable
        """
        return self._request("POST", f"/links/{link_id}/disable")

    # -----------------------------------------------------------------------
    # 策略管理
    # -----------------------------------------------------------------------

    def list_policies(
        self,
        policy_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        列出所有策略。

        GET /policies
        """
        params: Dict[str, str] = {}
        if policy_type:
            params["type"] = policy_type
        if status:
            params["status"] = status
        data = self._request("GET", "/policies", params=params)
        return data.get("policies", [])

    def get_policy(self, policy_id: str) -> Dict[str, Any]:
        """
        获取策略详情。

        GET /policies/{policy_id}
        """
        data = self._request("GET", f"/policies/{policy_id}")
        return data.get("policy", data)

    def create_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建策略。

        POST /policies
        """
        return self._request("POST", "/policies", json={"policy": policy})

    def update_policy(self, policy_id: str, policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新策略。

        PUT /policies/{policy_id}
        """
        return self._request("PUT", f"/policies/{policy_id}", json={"policy": policy})

    def delete_policy(self, policy_id: str) -> Dict[str, Any]:
        """
        删除策略。

        DELETE /policies/{policy_id}
        """
        return self._request("DELETE", f"/policies/{policy_id}")

    def apply_policy(
        self,
        policy_id: str,
        target_nodes: Optional[List[str]] = None,
        target_links: Optional[List[str]] = None,
        target_flows: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        应用策略到目标对象。

        POST /policies/{policy_id}/apply
        """
        payload = {
            "target_nodes": target_nodes or [],
            "target_links": target_links or [],
            "target_flows": target_flows or [],
        }
        return self._request("POST", f"/policies/{policy_id}/apply", json=payload)

    def revoke_policy(
        self,
        policy_id: str,
        target_nodes: Optional[List[str]] = None,
        target_links: Optional[List[str]] = None,
        target_flows: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        撤销已应用的策略。

        POST /policies/{policy_id}/revoke
        """
        payload = {
            "target_nodes": target_nodes or [],
            "target_links": target_links or [],
            "target_flows": target_flows or [],
        }
        return self._request("POST", f"/policies/{policy_id}/revoke", json=payload)

    # -----------------------------------------------------------------------
    # 统计与监控
    # -----------------------------------------------------------------------

    def get_node_stats(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取节点性能统计。

        GET /nodes/stats
        """
        params: Dict[str, str] = {}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        data = self._request("GET", "/nodes/stats", params=params)
        return data.get("stats", [])

    def get_link_stats(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取连接性能统计。

        GET /links/stats
        """
        params: Dict[str, str] = {}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        data = self._request("GET", "/links/stats", params=params)
        return data.get("stats", [])

    def get_alerts(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取安全告警。

        GET /alerts
        """
        params: Dict[str, str] = {}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        if severity:
            params["severity"] = severity
        data = self._request("GET", "/alerts", params=params)
        return data.get("alerts", [])

    # -----------------------------------------------------------------------
    # 蜜罐管理
    # -----------------------------------------------------------------------

    def get_honeypot_logs(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取蜜罐日志。

        GET /honeypot/logs
        """
        params: Dict[str, str] = {}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        data = self._request("GET", "/honeypot/logs", params=params)
        return data.get("logs", [])


# ---------------------------------------------------------------------------
# 便捷函数：获取当前应用上下文中的客户端实例
# ---------------------------------------------------------------------------


_client_instance: Optional[ControllerClient] = None
_client_lock = threading.Lock()


def get_controller_client() -> ControllerClient:
    """获取全局 ControllerClient 单例（懒加载）。"""
    global _client_instance
    with _client_lock:
        if _client_instance is None:
            _client_instance = ControllerClient()
        return _client_instance


def reset_controller_client() -> None:
    """重置全局客户端实例（用于测试或配置变更）。"""
    global _client_instance
    with _client_lock:
        _client_instance = None
