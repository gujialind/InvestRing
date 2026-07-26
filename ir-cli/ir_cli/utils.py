"""
命令层共享工具

- build_body / resolve_body: 请求体构造（过滤 None、支持 --json 直传）
- project_fields: 输出字段裁剪（降低 AI agent 上下文消耗）
- run_list: 列表命令统一执行（--all 全量翻页 + --fields 裁剪）
"""
import json
from typing import Any, Optional

from ir_cli.client import APIClient
from ir_cli.output import error, success


def build_body(**kwargs) -> dict:
    """过滤 None 值，构造请求体"""
    return {k: v for k, v in kwargs.items() if v is not None}


def resolve_body(json_body: Optional[str], required: tuple = (), **kwargs) -> dict:
    """
    构造请求体：--json 直传优先，否则由逐项参数构造。

    Args:
        json_body: --json 选项传入的完整 JSON 请求体字符串
        required: 必填字段名列表（无论来源，缺失即报 VALIDATION_ERROR）
        **kwargs: 逐项参数（None 值被过滤）
    """
    if json_body is not None:
        try:
            body = json.loads(json_body)
        except json.JSONDecodeError as e:
            error("INVALID_JSON", f"--json 参数不是合法 JSON: {e}")
        if not isinstance(body, dict):
            error("INVALID_JSON", "--json 参数必须是 JSON 对象")
    else:
        body = build_body(**kwargs)
    missing = [k for k in required if body.get(k) is None]
    if missing:
        error("VALIDATION_ERROR", f"缺少必填字段: {', '.join(missing)}")
    return body


def project_fields(data: Any, fields: Optional[str]) -> Any:
    """按逗号分隔的字段列表裁剪 dict / list[dict] 输出"""
    if not fields:
        return data
    keys = [f.strip() for f in fields.split(",") if f.strip()]
    if not keys:
        return data
    if isinstance(data, list):
        return [{k: it.get(k) for k in keys} if isinstance(it, dict) else it for it in data]
    if isinstance(data, dict):
        return {k: data.get(k) for k in keys}
    return data


def run_list(
    client: APIClient,
    path: str,
    params: Optional[dict] = None,
    page: int = 1,
    page_size: int = 20,
    all_pages: bool = False,
    fields: Optional[str] = None,
) -> None:
    """执行列表查询并输出：--all 时自动翻完所有页，--fields 时裁剪输出字段"""
    params = dict(params or {})
    if all_pages:
        result = client.get_all(path, params=params)
    else:
        params["page"] = page
        params["page_size"] = page_size
        result = client.get(path, params=params)
    success(data=project_fields(result["data"], fields), meta=result.get("meta"))
