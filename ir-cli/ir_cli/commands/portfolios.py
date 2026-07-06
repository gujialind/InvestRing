"""组合管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_portfolios(
    status: Optional[str] = typer.Option(None, "--status", help="状态筛选(draft/active/closed)"),
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """获取组合列表"""
    client = APIClient.from_config()
    params = {"page": page, "page_size": page_size}
    if status is not None:
        params["status"] = status
    result = client.get("/api/portfolios", params=params)
    success(data=result["data"], meta=result.get("meta"))


@app.command("create")
def create(
    code: str = typer.Option(..., "--code", help="组合代码"),
    name: str = typer.Option(..., "--name", help="组合名称"),
    description: Optional[str] = typer.Option(None, "--description", help="描述"),
):
    """创建组合"""
    client = APIClient.from_config()
    body = {"code": code, "name": name}
    if description is not None:
        body["description"] = description
    result = client.post("/api/portfolios", json_data=body)
    success(data=result["data"])


@app.command("get")
def get(code: str = typer.Argument(..., help="组合代码")):
    """获取组合详情"""
    client = APIClient.from_config()
    result = client.get(f"/api/portfolios/{code}")
    success(data=result["data"])


@app.command("update")
def update(
    code: str = typer.Argument(..., help="组合代码"),
    name: Optional[str] = typer.Option(None, "--name", help="组合名称"),
    description: Optional[str] = typer.Option(None, "--description", help="描述"),
):
    """更新组合信息"""
    client = APIClient.from_config()
    body = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    result = client.put(f"/api/portfolios/{code}", json_data=body)
    success(data=result["data"])


@app.command("close")
def close(code: str = typer.Argument(..., help="组合代码")):
    """关闭组合"""
    client = APIClient.from_config()
    result = client.post(f"/api/portfolios/{code}/close")
    success(data=result["data"])


@app.command("reactivate")
def reactivate(code: str = typer.Argument(..., help="组合代码")):
    """重新激活组合"""
    client = APIClient.from_config()
    result = client.post(f"/api/portfolios/{code}/reactivate")
    success(data=result["data"])


@app.command("nav-history")
def nav_history(
    code: str = typer.Argument(..., help="组合代码"),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="开始日期(YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="结束日期(YYYY-MM-DD)"),
):
    """获取净值历史"""
    client = APIClient.from_config()
    params = {}
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    result = client.get(f"/api/portfolios/{code}/nav-history", params=params)
    success(data=result["data"])


@app.command("returns")
def returns(code: str = typer.Argument(..., help="组合代码")):
    """获取收益率"""
    client = APIClient.from_config()
    result = client.get(f"/api/portfolios/{code}/returns")
    success(data=result["data"])


@app.command("cash-flow")
def cash_flow(code: str = typer.Argument(..., help="组合代码")):
    """获取资金流"""
    client = APIClient.from_config()
    result = client.get(f"/api/portfolios/{code}/cash-flow")
    success(data=result["data"])
