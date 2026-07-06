"""调仓交易管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_trades(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="组合代码"),
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """获取交易列表"""
    client = APIClient.from_config()
    params = {"page": page, "page_size": page_size}
    if portfolio_code is not None:
        params["portfolio_code"] = portfolio_code
    result = client.get("/api/trades", params=params)
    success(data=result["data"], meta=result.get("meta"))


@app.command("create")
def create(
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
    product_code: str = typer.Option(..., "--product-code", help="产品代码"),
    trade_type: str = typer.Option(..., "--type", help="类型(buy/sell)"),
    trade_date: str = typer.Option(..., "--trade-date", help="交易日期(YYYY-MM-DD)"),
    actual_amount: Optional[float] = typer.Option(None, "--actual-amount", help="实际金额"),
    fee: float = typer.Option(0, "--fee", help="手续费"),
    platform_code: Optional[str] = typer.Option(None, "--platform-code", help="平台代码"),
    market: Optional[str] = typer.Option(None, "--market", help="市场类型"),
    price: Optional[float] = typer.Option(None, "--price", help="价格"),
    shares: Optional[float] = typer.Option(None, "--shares", help="份额"),
    amount: Optional[float] = typer.Option(None, "--amount", help="金额"),
    notes: Optional[str] = typer.Option(None, "--notes", help="备注"),
):
    """创建交易"""
    client = APIClient.from_config()
    body = {
        "portfolio_code": portfolio_code,
        "product_code": product_code,
        "trade_type": trade_type,
        "trade_date": trade_date,
        "fee": fee,
    }
    if actual_amount is not None:
        body["actual_amount"] = actual_amount
    if platform_code is not None:
        body["platform_code"] = platform_code
    if market is not None:
        body["market"] = market
    if price is not None:
        body["price"] = price
    if shares is not None:
        body["shares"] = shares
    if amount is not None:
        body["amount"] = amount
    if notes is not None:
        body["notes"] = notes
    result = client.post("/api/trades", json_data=body)
    success(data=result["data"])


@app.command("get")
def get(id: int = typer.Argument(..., help="交易ID")):
    """获取交易详情"""
    client = APIClient.from_config()
    result = client.get(f"/api/trades/{id}")
    success(data=result["data"])


@app.command("confirm")
def confirm(
    id: int = typer.Argument(..., help="交易ID"),
    confirm_date: Optional[str] = typer.Option(None, "--confirm-date", help="确认日期(YYYY-MM-DD)"),
    price: Optional[float] = typer.Option(None, "--price", help="确认价格"),
):
    """确认交易"""
    client = APIClient.from_config()
    params = {}
    if confirm_date is not None:
        params["confirm_date"] = confirm_date
    if price is not None:
        params["price"] = price
    result = client.post(f"/api/trades/{id}/confirm", params=params)
    success(data=result["data"])


@app.command("cancel")
def cancel(id: int = typer.Argument(..., help="交易ID")):
    """取消交易"""
    client = APIClient.from_config()
    result = client.post(f"/api/trades/{id}/cancel")
    success(data=result["data"])


@app.command("unconfirm")
def unconfirm(id: int = typer.Argument(..., help="交易ID")):
    """取消确认"""
    client = APIClient.from_config()
    result = client.post(f"/api/trades/{id}/unconfirm")
    success(data=result["data"])
