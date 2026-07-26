"""
HTTP 客户端封装

所有命令通过此模块与后端通信，统一处理认证、错误和响应格式。
"""
import os
from typing import Any, Optional

import httpx

from ir_cli import config
from ir_cli.output import EXIT_AUTH, EXIT_CONNECTION, error, success


class APIClient:
    """HTTP API 客户端"""

    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # 连接超时短（快速发现服务不可达），读超时长（兼容快照重算等长任务）
        timeout = httpx.Timeout(
            connect=float(os.environ.get("IR_CONNECT_TIMEOUT", "5")),
            read=float(os.environ.get("IR_HTTP_TIMEOUT", "300")),
            write=30.0,
            pool=5.0,
        )
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
        )

    @classmethod
    def from_config(cls, require_auth: bool = True) -> "APIClient":
        """从配置文件读取 base_url 和 token"""
        base_url = config.get_base_url()
        token_data = config.load_token()
        token = token_data["token"] if token_data else None
        if require_auth and not token:
            error("AUTH_REQUIRED", "未登录或 token 已过期，请执行: ir auth login", exit_code=EXIT_AUTH)
        return cls(base_url, token)

    def _handle_response(self, resp: httpx.Response) -> dict:
        """统一处理 HTTP 响应"""
        if resp.status_code >= 400:
            default_code = {
                401: "AUTH_REQUIRED",
                403: "FORBIDDEN",
                404: "NOT_FOUND",
                409: "CONFLICT",
                422: "VALIDATION_ERROR",
            }.get(resp.status_code, "SERVER_ERROR" if resp.status_code >= 500 else "HTTP_ERROR")
            code = self._extract_error_code(resp, default_code)
            detail = self._extract_detail(resp)
            # 后端无结构化 message 时使用友好提示兜底
            if detail.startswith(f"HTTP {resp.status_code}"):
                fallback = {
                    401: "认证失败或 token 已过期，请执行: ir auth login",
                    403: "无权限执行此操作",
                }.get(resp.status_code)
                if fallback:
                    detail = fallback
            error(
                code,
                detail,
                details={"http_status": resp.status_code},
                exit_code=EXIT_AUTH if resp.status_code == 401 else 1,
            )

        # 2xx 成功
        try:
            body = resp.json()
        except Exception:
            return {"data": resp.text}

        # 分页响应: {items: [...], total, page, page_size}
        if isinstance(body, dict) and "items" in body and "total" in body:
            total = body["total"]
            page = body.get("page")
            page_size = body.get("page_size")
            has_more = None
            if page is not None and page_size is not None:
                has_more = page * page_size < total
            return {
                "data": body["items"],
                "meta": {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "has_more": has_more,
                },
            }
        return {"data": body}

    def _extract_detail(self, resp: httpx.Response) -> str:
        """从错误响应中提取 detail 消息"""
        try:
            body = resp.json()
            detail = body.get("detail", "")
            if isinstance(detail, dict):
                return detail.get("message", str(detail))
            return str(detail) if detail else f"HTTP {resp.status_code}"
        except Exception:
            return f"HTTP {resp.status_code}: {resp.text[:200]}"

    def _extract_error_code(self, resp: httpx.Response, default: str) -> str:
        """从错误响应中提取后端结构化业务错误码（detail.error），缺失时用默认码"""
        try:
            body = resp.json()
            detail = body.get("detail", {})
            if isinstance(detail, dict):
                return detail.get("error", default)
        except Exception:
            pass
        return default

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        """GET 请求"""
        try:
            resp = self._client.get(path, params=params)
        except httpx.ConnectError:
            error("CONNECTION_ERROR", f"无法连接到 {self.base_url}，请检查 IR_BASE_URL 配置", exit_code=EXIT_CONNECTION)
        except httpx.TimeoutException:
            error("TIMEOUT_ERROR", f"请求超时: {self.base_url}{path}", exit_code=EXIT_CONNECTION)
        return self._handle_response(resp)

    def post(self, path: str, json_data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        """POST 请求"""
        try:
            resp = self._client.post(path, json=json_data, params=params)
        except httpx.ConnectError:
            error("CONNECTION_ERROR", f"无法连接到 {self.base_url}，请检查 IR_BASE_URL 配置", exit_code=EXIT_CONNECTION)
        except httpx.TimeoutException:
            error("TIMEOUT_ERROR", f"请求超时: {self.base_url}{path}", exit_code=EXIT_CONNECTION)
        return self._handle_response(resp)

    def put(self, path: str, json_data: Optional[dict] = None) -> dict:
        """PUT 请求"""
        try:
            resp = self._client.put(path, json=json_data)
        except httpx.ConnectError:
            error("CONNECTION_ERROR", f"无法连接到 {self.base_url}，请检查 IR_BASE_URL 配置", exit_code=EXIT_CONNECTION)
        except httpx.TimeoutException:
            error("TIMEOUT_ERROR", f"请求超时: {self.base_url}{path}", exit_code=EXIT_CONNECTION)
        return self._handle_response(resp)

    def delete(self, path: str, params: Optional[dict] = None) -> dict:
        """DELETE 请求"""
        try:
            resp = self._client.delete(path, params=params)
        except httpx.ConnectError:
            error("CONNECTION_ERROR", f"无法连接到 {self.base_url}，请检查 IR_BASE_URL 配置", exit_code=EXIT_CONNECTION)
        except httpx.TimeoutException:
            error("TIMEOUT_ERROR", f"请求超时: {self.base_url}{path}", exit_code=EXIT_CONNECTION)
        return self._handle_response(resp)

    def get_all(self, path: str, params: Optional[dict] = None) -> dict:
        """分页获取所有记录"""
        params = dict(params or {})
        params["page_size"] = 100
        params["page"] = 1

        all_items = []
        while True:
            result = self.get(path, params=params)
            items = result.get("data", [])
            all_items.extend(items)
            meta = result.get("meta", {})
            total = meta.get("total", 0)
            if len(all_items) >= total or not items:
                break
            params["page"] += 1

        return {
            "data": all_items,
            "meta": {"total": len(all_items), "has_more": False},
        }

    def close(self):
        """关闭 HTTP 客户端"""
        self._client.close()
