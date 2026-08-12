"""
领域异常（Business Error）

统一的业务异常载体，供 service 层抛出、router 全局处理器映射：
- router：FastAPI 异常处理器 → JSONResponse(detail={"error": code, "message": message})

service 层只抛本模块（或其子类）异常，不 import fastapi、不感知 HTTP。
"""
from typing import Optional


class BusinessError(Exception):
    """业务规则违反异常。

    Attributes:
        code: 稳定的错误码（如 NON_TRADING_DAY），REST 共用
        message: 人类可读描述
        http_status: REST 层映射的 HTTP 状态码（默认 422 业务校验失败）
        details: 额外结构化信息（可选）
    """

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = 422,
        details: Optional[dict] = None,
    ):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details
        super().__init__(message)


class NotFoundError(BusinessError):
    """资源不存在（映射 404）。"""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(code, message, http_status=404, details=details)
