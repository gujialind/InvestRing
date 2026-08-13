"""资产分类维度字典管理命令组（issue #135）"""
from typing import Optional

import typer

from ir_cli.client import APIClient
from ir_cli.output import error, success
from ir_cli.utils import SUMMARY_FIELDS, resolve_body, run_list

app = typer.Typer(no_args_is_help=True)

_DIMENSIONS = "asset_class/region/style/size/segment"
_RULES = "required/optional"


def _parse_rules(rules: Optional[list[str]]) -> Optional[dict]:
    """解析重复 flag --rule dimension=rule 为 dict（全量替换语义）"""
    if rules is None:
        return None
    parsed = {}
    for item in rules:
        if "=" not in item:
            error("VALIDATION_ERROR", f"--rule 格式须为 dimension=rule（如 region=required），收到: {item}")
        dimension, rule = item.split("=", 1)
        parsed[dimension.strip()] = rule.strip()
    return parsed


def _parse_applicable(applicable: Optional[str]) -> Optional[list]:
    """解析逗号多值 --applicable 为 list（全量替换语义）"""
    if applicable is None:
        return None
    return [c.strip() for c in applicable.split(",") if c.strip()]


@app.command("list")
def list_classifications(
    dimension: Optional[str] = typer.Option(None, "--dimension", help=f"按维度过滤({_DIMENSIONS})"),
    fields: Optional[str] = typer.Option(None, "--fields", help="仅输出指定字段(逗号分隔)"),
    full: bool = typer.Option(False, "--full", help="输出全部字段"),
):
    """获取维度值字典（含停用值；维度级规则矩阵见 get 单条或 API 顶层 dimension_rules）"""
    client = APIClient.from_config()
    params = {"dimension": dimension} if dimension else {}
    run_list(
        client, "/api/asset-classifications", params=params,
        fields=fields, full=full,
        default_fields=SUMMARY_FIELDS["asset_classification"],
    )


@app.command("get")
def get(code: str = typer.Argument(..., help="维度值代码")):
    """获取维度值详情（asset_class 维度值附 dimension_rules 维度规则）"""
    client = APIClient.from_config()
    result = client.get(f"/api/asset-classifications/{code}")
    success(data=result["data"])


@app.command("create")
def create(
    code: Optional[str] = typer.Option(None, "--code", help="维度值代码(必填，全大写，前缀须匹配维度: ASSET_/REGION_/STYLE_/SIZE_/SEG_)"),
    dimension: Optional[str] = typer.Option(None, "--dimension", help=f"所属维度(必填，{_DIMENSIONS})"),
    name: Optional[str] = typer.Option(None, "--name", help="显示名称(必填)"),
    sort_order: Optional[int] = typer.Option(None, "--sort-order", help="排序号(asset_class 的序位即前端色板序位，变更即改色)"),
    description: Optional[str] = typer.Option(None, "--description", help="描述"),
    applicable: Optional[str] = typer.Option(None, "--applicable", help="适用大类(逗号分隔，如 ASSET_STOCK,ASSET_BOND；非 asset_class 维度必填且目标规则须允许该维度)"),
    rule: Optional[list[str]] = typer.Option(None, "--rule", help=f"维度规则(仅 asset_class，可重复，如 --rule region=required；rule ∈ {_RULES}，缺省=现金型全禁止)"),
    json_body: Optional[str] = typer.Option(None, "--json", help="完整 JSON 请求体，优先于逐项参数"),
):
    """新建维度值（无删除命令，后悔药用 update --inactive 软失效）"""
    client = APIClient.from_config()
    body = resolve_body(
        json_body,
        required=("code", "dimension", "name"),
        code=code,
        dimension=dimension,
        name=name,
        sort_order=sort_order,
        description=description,
        applicable_asset_classes=_parse_applicable(applicable),
        dimension_rules=_parse_rules(rule),
    )
    result = client.post("/api/asset-classifications", json_data=body)
    success(data=result["data"])


@app.command("update")
def update(
    code: str = typer.Argument(..., help="维度值代码"),
    name: Optional[str] = typer.Option(None, "--name", help="显示名称"),
    sort_order: Optional[int] = typer.Option(None, "--sort-order", help="排序号(asset_class 的序位即前端色板序位，变更即改色)"),
    description: Optional[str] = typer.Option(None, "--description", help="描述"),
    is_active: Optional[bool] = typer.Option(None, "--active/--inactive", help="启用/停用(软失效，存量引用不阻断)"),
    applicable: Optional[str] = typer.Option(None, "--applicable", help="适用大类(逗号分隔，全量替换；移除被引用关联报 DIMENSION_VALUE_IN_USE，不可减到 0)"),
    rule: Optional[list[str]] = typer.Option(None, "--rule", help=f"维度规则(仅 asset_class，全量替换，可重复；rule ∈ {_RULES}，未出现的维度=禁止；收紧有存量冲突保护 DIMENSION_RULE_CONFLICT)"),
    json_body: Optional[str] = typer.Option(None, "--json", help="完整 JSON 请求体，优先于逐项参数"),
):
    """更新维度值（code/dimension 不可改；关联与规则为全量替换语义）"""
    client = APIClient.from_config()
    body = resolve_body(
        json_body,
        name=name,
        sort_order=sort_order,
        description=description,
        is_active=is_active,
        applicable_asset_classes=_parse_applicable(applicable),
        dimension_rules=_parse_rules(rule),
    )
    if not body:
        error("VALIDATION_ERROR", "未提供任何更新字段")
    result = client.put(f"/api/asset-classifications/{code}", json_data=body)
    success(data=result["data"])
