"""申购赎回管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_subs(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="组合代码"),
    investor_code: Optional[str] = typer.Option(None, "--investor-code", help="投资人代码"),
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """获取申赎列表"""
    client = APIClient.from_config()
    params = {"page": page, "page_size": page_size}
    if portfolio_code is not None:
        params["portfolio_code"] = portfolio_code
    if investor_code is not None:
        params["investor_code"] = investor_code
    result = client.get("/api/subscriptions", params=params)
    success(data=result["data"], meta=result.get("meta"))


@app.command("create")
def create(
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
    investor_code: str = typer.Option(..., "--investor-code", help="投资人代码"),
    sub_type: str = typer.Option(..., "--type", help="类型(subscribe/redeem)"),
    apply_date: str = typer.Option(..., "--apply-date", help="申请日期(YYYY-MM-DD)"),
    amount: Optional[float] = typer.Option(None, "--amount", help="金额(申购用)"),
    shares: Optional[float] = typer.Option(None, "--shares", help="份额(赎回用)"),
    unit_price: Optional[float] = typer.Option(None, "--unit-price", help="净值"),
    platform_code: str = typer.Option(..., "--platform-code", help="交易平台代码"),
    notes: Optional[str] = typer.Option(None, "--notes", help="备注"),
):
    """创建申赎申请"""
    client = APIClient.from_config()
    body = {
        "portfolio_code": portfolio_code,
        "investor_code": investor_code,
        "sub_type": sub_type,
        "apply_date": apply_date,
        "platform_code": platform_code,
    }
    if amount is not None:
        body["amount"] = amount
    if shares is not None:
        body["shares"] = shares
    if unit_price is not None:
        body["unit_price"] = unit_price
    if notes is not None:
        body["notes"] = notes
    result = client.post("/api/subscriptions", json_data=body)
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
):
    """更新申赎（仅 pending 可改，confirmed 需先 unconfirm）"""
    client = APIClient.from_config()
    body = {}
    for k, v in {
        "amount": amount, "shares": shares, "unit_price": unit_price,
        "platform_code": platform_code, "confirm_date": confirm_date, "notes": notes,
    }.items():
        if v is not None:
            body[k] = v
    if not body:
        typer.echo("未提供任何更新字段")
        raise typer.Exit(code=1)
    result = client.put(f"/api/subscriptions/{id}", json_data=body)
    success(data=result["data"])


@app.command("delete")
def delete(id: int = typer.Argument(..., help="申赎ID")):
    """删除申赎（仅 pending 可删，confirmed 需先 unconfirm）"""
    client = APIClient.from_config()
    result = client.delete(f"/api/subscriptions/{id}")
    success(data=result["data"])
