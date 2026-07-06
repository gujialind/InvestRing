"""份额变动事件管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_events(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="组合代码"),
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """获取份额变动事件列表"""
    client = APIClient.from_config()
    params = {"page": page, "page_size": page_size}
    if portfolio_code is not None:
        params["portfolio_code"] = portfolio_code
    result = client.get("/api/share-change-events", params=params)
    success(data=result["data"], meta=result.get("meta"))


@app.command("create")
def create(
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
    event_type: str = typer.Option(..., "--event-type", help="事件类型"),
    event_date: str = typer.Option(..., "--event-date", help="事件日期(YYYY-MM-DD)"),
    entitlement_date: str = typer.Option(..., "--entitlement-date", help="权益登记日(YYYY-MM-DD)"),
    product_code: Optional[str] = typer.Option(None, "--product-code", help="产品代码"),
    market: Optional[str] = typer.Option(None, "--market", help="市场类型"),
    entitlement_shares: Optional[float] = typer.Option(None, "--entitlement-shares", help="权益份额"),
    div_cash: Optional[float] = typer.Option(None, "--div-cash", help="每股分红金额"),
    reinvest_nav: Optional[float] = typer.Option(None, "--reinvest-nav", help="再投资净值"),
    ratio: Optional[float] = typer.Option(None, "--ratio", help="拆分/合并比例"),
    shares_change: Optional[float] = typer.Option(None, "--shares-change", help="份额变化量"),
    cash_change: Optional[float] = typer.Option(None, "--cash-change", help="现金变化量"),
    notes: Optional[str] = typer.Option(None, "--notes", help="备注"),
):
    """创建份额变动事件"""
    client = APIClient.from_config()
    body = {
        "portfolio_code": portfolio_code,
        "event_type": event_type,
        "event_date": event_date,
        "entitlement_date": entitlement_date,
    }
    for k, v in {
        "product_code": product_code, "market": market,
        "entitlement_shares": entitlement_shares, "div_cash": div_cash,
        "reinvest_nav": reinvest_nav, "ratio": ratio,
        "shares_change": shares_change, "cash_change": cash_change,
        "notes": notes,
    }.items():
        if v is not None:
            body[k] = v
    result = client.post("/api/share-change-events", json_data=body)
    success(data=result["data"])


@app.command("get")
def get(id: int = typer.Argument(..., help="事件ID")):
    """获取事件详情"""
    client = APIClient.from_config()
    result = client.get(f"/api/share-change-events/{id}")
    success(data=result["data"])


@app.command("update")
def update(
    id: int = typer.Argument(..., help="事件ID"),
    event_date: Optional[str] = typer.Option(None, "--event-date", help="事件日期"),
    entitlement_date: Optional[str] = typer.Option(None, "--entitlement-date", help="权益登记日"),
    div_cash: Optional[float] = typer.Option(None, "--div-cash", help="每股分红金额"),
    reinvest_nav: Optional[float] = typer.Option(None, "--reinvest-nav", help="再投资净值"),
    ratio: Optional[float] = typer.Option(None, "--ratio", help="比例"),
    shares_change: Optional[float] = typer.Option(None, "--shares-change", help="份额变化量"),
    cash_change: Optional[float] = typer.Option(None, "--cash-change", help="现金变化量"),
    notes: Optional[str] = typer.Option(None, "--notes", help="备注"),
):
    """更新事件"""
    client = APIClient.from_config()
    body = {}
    for k, v in {
        "event_date": event_date, "entitlement_date": entitlement_date,
        "div_cash": div_cash, "reinvest_nav": reinvest_nav,
        "ratio": ratio, "shares_change": shares_change,
        "cash_change": cash_change, "notes": notes,
    }.items():
        if v is not None:
            body[k] = v
    result = client.put(f"/api/share-change-events/{id}", json_data=body)
    success(data=result["data"])


@app.command("delete")
def delete(id: int = typer.Argument(..., help="事件ID")):
    """删除事件"""
    client = APIClient.from_config()
    result = client.delete(f"/api/share-change-events/{id}")
    success(data=result["data"])


@app.command("confirm")
def confirm(id: int = typer.Argument(..., help="事件ID")):
    """确认事件"""
    client = APIClient.from_config()
    result = client.post(f"/api/share-change-events/{id}/confirm")
    success(data=result["data"])


@app.command("cancel")
def cancel(id: int = typer.Argument(..., help="事件ID")):
    """取消事件"""
    client = APIClient.from_config()
    result = client.post(f"/api/share-change-events/{id}/cancel")
    success(data=result["data"])
