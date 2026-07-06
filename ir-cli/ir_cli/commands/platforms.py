"""平台管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_platforms(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """获取平台列表"""
    client = APIClient.from_config()
    result = client.get("/api/platforms", params={"page": page, "page_size": page_size})
    success(data=result["data"], meta=result.get("meta"))


@app.command("create")
def create(
    code: str = typer.Option(..., "--code", help="平台代码"),
    name: str = typer.Option(..., "--name", help="平台名称"),
    platform_type: Optional[str] = typer.Option(None, "--platform-type", help="平台类型"),
):
    """创建平台"""
    client = APIClient.from_config()
    body = {"code": code, "name": name}
    if platform_type is not None:
        body["platform_type"] = platform_type
    result = client.post("/api/platforms", json_data=body)
    success(data=result["data"])


@app.command("get")
def get(code: str = typer.Argument(..., help="平台代码")):
    """获取平台详情"""
    client = APIClient.from_config()
    result = client.get(f"/api/platforms/{code}")
    success(data=result["data"])


@app.command("update")
def update(
    code: str = typer.Argument(..., help="平台代码"),
    name: Optional[str] = typer.Option(None, "--name", help="平台名称"),
    platform_type: Optional[str] = typer.Option(None, "--platform-type", help="平台类型"),
):
    """更新平台"""
    client = APIClient.from_config()
    body = {}
    if name is not None:
        body["name"] = name
    if platform_type is not None:
        body["platform_type"] = platform_type
    result = client.put(f"/api/platforms/{code}", json_data=body)
    success(data=result["data"])


@app.command("delete")
def delete(code: str = typer.Argument(..., help="平台代码")):
    """删除平台"""
    client = APIClient.from_config()
    result = client.delete(f"/api/platforms/{code}")
    success(data=result["data"])
