"""产品管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_products(
    product_type: Optional[str] = typer.Option(None, "--product-type", help="产品类型(ETF/OEF/LOF/CASH)"),
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """获取产品列表"""
    client = APIClient.from_config()
    params = {"page": page, "page_size": page_size}
    if product_type is not None:
        params["product_type"] = product_type
    result = client.get("/api/products", params=params)
    success(data=result["data"], meta=result.get("meta"))


@app.command("create")
def create(
    code: str = typer.Option(..., "--code", help="产品代码"),
    name: str = typer.Option(..., "--name", help="产品名称"),
    product_type: str = typer.Option(..., "--product-type", help="产品类型(ETF/OEF/LOF/CASH)"),
    market: Optional[str] = typer.Option(None, "--market", help="市场类型"),
    asset_class_code: Optional[str] = typer.Option(None, "--asset-class-code", help="资产分类代码"),
    confirm_days: int = typer.Option(1, "--confirm-days", help="确认天数"),
    is_qdii: bool = typer.Option(False, "--is-qdii/--no-qdii", help="是否QDII"),
):
    """创建产品"""
    client = APIClient.from_config()
    body = {
        "code": code, "name": name, "product_type": product_type,
        "confirm_days": confirm_days, "is_qdii": is_qdii,
    }
    if market is not None:
        body["market"] = market
    if asset_class_code is not None:
        body["asset_class_code"] = asset_class_code
    result = client.post("/api/products", json_data=body)
    success(data=result["data"])


@app.command("get")
def get(
    code: str = typer.Argument(..., help="产品代码"),
    market: str = typer.Argument(..., help="市场类型"),
):
    """获取产品详情"""
    client = APIClient.from_config()
    result = client.get(f"/api/products/{code}/{market}")
    success(data=result["data"])


@app.command("update")
def update(
    code: str = typer.Argument(..., help="产品代码"),
    market: str = typer.Argument(..., help="市场类型"),
    name: Optional[str] = typer.Option(None, "--name", help="产品名称"),
    asset_class_code: Optional[str] = typer.Option(None, "--asset-class-code", help="资产分类代码"),
    confirm_days: Optional[int] = typer.Option(None, "--confirm-days", help="确认天数"),
    is_qdii: Optional[bool] = typer.Option(None, "--is-qdii/--no-qdii", help="是否QDII"),
):
    """更新产品"""
    client = APIClient.from_config()
    body = {}
    if name is not None:
        body["name"] = name
    if asset_class_code is not None:
        body["asset_class_code"] = asset_class_code
    if confirm_days is not None:
        body["confirm_days"] = confirm_days
    if is_qdii is not None:
        body["is_qdii"] = is_qdii
    result = client.put(f"/api/products/{code}/{market}", json_data=body)
    success(data=result["data"])


@app.command("delete")
def delete(
    code: str = typer.Argument(..., help="产品代码"),
    market: str = typer.Argument(..., help="市场类型"),
):
    """删除产品"""
    client = APIClient.from_config()
    result = client.delete(f"/api/products/{code}/{market}")
    success(data=result["data"])
