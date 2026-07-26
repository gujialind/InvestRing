"""申购赎回管理命令组"""
import sys
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import error, success
from ir_cli.utils import build_body, resolve_body, run_list

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_subs(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="组合代码"),
    investor_code: Optional[str] = typer.Option(None, "--investor-code", help="投资人代码"),
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
    all_pages: bool = typer.Option(False, "--all", help="自动翻页获取全部记录"),
    fields: Optional[str] = typer.Option(None, "--fields", help="仅输出指定字段(逗号分隔)"),
):
    """获取申赎列表"""
    client = APIClient.from_config()
    params = build_body(portfolio_code=portfolio_code, investor_code=investor_code)
    run_list(client, "/api/subscriptions", params, page=page, page_size=page_size, all_pages=all_pages, fields=fields)


@app.command("create")
def create(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="组合代码(必填)"),
    investor_code: Optional[str] = typer.Option(None, "--investor-code", help="投资人代码(必填)"),
    sub_type: Optional[str] = typer.Option(None, "--type", help="类型(subscribe/redeem)(必填)"),
    apply_date: Optional[str] = typer.Option(None, "--apply-date", help="申请日期(YYYY-MM-DD)(必填)"),
    amount: Optional[float] = typer.Option(None, "--amount", help="金额(申购用)"),
    shares: Optional[float] = typer.Option(None, "--shares", help="份额(赎回用)"),
    unit_price: Optional[float] = typer.Option(None, "--unit-price", help="净值"),
    platform_code: Optional[str] = typer.Option(None, "--platform-code", help="交易平台代码(必填)"),
    notes: Optional[str] = typer.Option(None, "--notes", help="备注"),
    json_body: Optional[str] = typer.Option(None, "--json", help="完整 JSON 请求体，优先于逐项参数"),
    auto_confirm: bool = typer.Option(False, "--confirm", help="创建成功后立即确认（快捷组合）"),
):
    """创建申赎申请（--confirm 可链式创建+确认）"""
    client = APIClient.from_config()
    body = resolve_body(
        json_body,
        required=("portfolio_code", "investor_code", "sub_type", "apply_date", "platform_code"),
        portfolio_code=portfolio_code,
        investor_code=investor_code,
        sub_type=sub_type,
        apply_date=apply_date,
        amount=amount,
        shares=shares,
        unit_price=unit_price,
        platform_code=platform_code,
        notes=notes,
    )
    result = client.post("/api/subscriptions", json_data=body)
    created = result["data"]
    if auto_confirm and isinstance(created, dict) and created.get("id"):
        # 确认失败时 stdout 为确认阶段的错误 JSON，stderr 保留已创建的 id 便于后续处理
        print(f"[info] 申赎已创建 id={created['id']}，正在确认...", file=sys.stderr)
        result = client.post(f"/api/subscriptions/{created['id']}/confirm")
    success(data=result["data"])


@app.command("get")
def get(id: int = typer.Argument(..., help="申赎ID")):
    """获取申赎详情"""
    client = APIClient.from_config()
    result = client.get(f"/api/subscriptions/{id}")
    success(data=result["data"])


@app.command("confirm")
def confirm(
    id: int = typer.Argument(..., help="申赎ID"),
):
    """确认申赎"""
    client = APIClient.from_config()
    result = client.post(f"/api/subscriptions/{id}/confirm")
    success(data=result["data"])


@app.command("cancel")
def cancel(id: int = typer.Argument(..., help="申赎ID")):
    """取消申赎"""
    client = APIClient.from_config()
    result = client.post(f"/api/subscriptions/{id}/cancel")
    success(data=result["data"])


@app.command("unconfirm")
def unconfirm(id: int = typer.Argument(..., help="申赎ID")):
    """取消确认"""
    client = APIClient.from_config()
    result = client.post(f"/api/subscriptions/{id}/unconfirm")
    success(data=result["data"])


@app.command("update")
def update(
    id: int = typer.Argument(..., help="申赎ID"),
    amount: Optional[float] = typer.Option(None, "--amount", help="金额"),
    shares: Optional[float] = typer.Option(None, "--shares", help="份额"),
    unit_price: Optional[float] = typer.Option(None, "--unit-price", help="净值"),
    platform_code: Optional[str] = typer.Option(None, "--platform-code", help="平台代码"),
    confirm_date: Optional[str] = typer.Option(None, "--confirm-date", help="确认日期(YYYY-MM-DD)"),
    notes: Optional[str] = typer.Option(None, "--notes", help="备注"),
    json_body: Optional[str] = typer.Option(None, "--json", help="完整 JSON 请求体，优先于逐项参数"),
):
    """更新申赎（仅 pending 可改，confirmed 需先 unconfirm）"""
    client = APIClient.from_config()
    body = resolve_body(
        json_body,
        amount=amount,
        shares=shares,
        unit_price=unit_price,
        platform_code=platform_code,
        confirm_date=confirm_date,
        notes=notes,
    )
    if not body:
        error("VALIDATION_ERROR", "未提供任何更新字段")
    result = client.put(f"/api/subscriptions/{id}", json_data=body)
    success(data=result["data"])


@app.command("delete")
def delete(id: int = typer.Argument(..., help="申赎ID")):
    """删除申赎（仅 pending 可删，confirmed 需先 unconfirm）"""
    client = APIClient.from_config()
    result = client.delete(f"/api/subscriptions/{id}")
    success(data=result["data"])
