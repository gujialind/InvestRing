"""
JSON 输出协议

统一输出格式：
- 成功: {"ok": true, "data": ..., "meta": ...}
- 失败: {"ok": false, "error": {"code": ..., "message": ...}}

退出码分层：
- 0: 成功
- 1: 业务错误（可换参数重试）
- 2: 认证错误（需 ir auth login）
- 3: 连接/超时错误（可原样重试或检查服务）
"""
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any, NoReturn, Optional


class InvestRingEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 Decimal/date/datetime 类型"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            # 字符串化避免 float 二进制误差（如 0.1+0.2 问题），agent 可直接用于金额比对
            return format(obj, "f")
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def _output(data: dict) -> None:
    """输出 JSON 到 stdout"""
    print(json.dumps(data, cls=InvestRingEncoder, ensure_ascii=False))


def success(data: Any, meta: Optional[dict] = None) -> None:
    """
    成功输出并退出（exit code 0）

    Args:
        data: 主要数据（dict/list/model dict）
        meta: 分页元数据 {"total", "page", "page_size"}
    """
    result = {"ok": True, "data": data}
    if meta:
        result["meta"] = meta
    _output(result)
    sys.exit(0)


# 退出码常量
EXIT_BUSINESS = 1
EXIT_AUTH = 2
EXIT_CONNECTION = 3


def error(code: str, message: str, details: Optional[dict] = None, exit_code: int = EXIT_BUSINESS) -> NoReturn:
    """
    错误输出并退出

    Args:
        code: 错误码，如 NOT_FOUND, VALIDATION_ERROR
        message: 人类可读错误描述
        details: 额外详情
        exit_code: 退出码（1=业务 2=认证 3=连接）
    """
    result: dict = {
        "ok": False,
        "error": {"code": code, "message": message},
    }
    if details:
        result["error"]["details"] = details
    _output(result)
    sys.exit(exit_code)
