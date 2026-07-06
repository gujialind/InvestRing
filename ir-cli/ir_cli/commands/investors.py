"""投资人管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_investors(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """获取投资人列表"""
    client = APIClient.from_config()
    result = client.get("/api/investors", params={"page": page, "page_size": page_size})
    success(data=result["data"], meta=result.get("meta"))


@app.command("create")
def create(
    code: str = typer.Option(..., "--code", help="投资人代码"),
    name: str = typer.Option(..., "--name", help="姓名"),
    password: str = typer.Option(..., "--password", help="密码"),
    phone: Optional[str] = typer.Option(None, "--phone", help="手机号"),
    email: Optional[str] = typer.Option(None, "--email", help="邮箱"),
):
    """创建投资人"""
    client = APIClient.from_config()
    body = {"code": code, "name": name, "password": password}
    if phone is not None:
        body["phone"] = phone
    if email is not None:
        body["email"] = email
    result = client.post("/api/investors", json_data=body)
    success(data=result["data"])


@app.command("get")
def get(code: str = typer.Argument(..., help="投资人代码")):
    """获取投资人详情"""
    client = APIClient.from_config()
    result = client.get(f"/api/investors/{code}")
    success(data=result["data"])


@app.command("update")
def update(
    code: str = typer.Argument(..., help="投资人代码"),
    name: Optional[str] = typer.Option(None, "--name", help="姓名"),
    phone: Optional[str] = typer.Option(None, "--phone", help="手机号"),
    email: Optional[str] = typer.Option(None, "--email", help="邮箱"),
    role: Optional[str] = typer.Option(None, "--role", help="角色(admin/viewer)"),
):
    """更新投资人信息"""
    client = APIClient.from_config()
    body = {}
    if name is not None:
        body["name"] = name
    if phone is not None:
        body["phone"] = phone
    if email is not None:
        body["email"] = email
    if role is not None:
        body["role"] = role
    result = client.put(f"/api/investors/{code}", json_data=body)
    success(data=result["data"])


@app.command("delete")
def delete(code: str = typer.Argument(..., help="投资人代码")):
    """删除投资人"""
    client = APIClient.from_config()
    result = client.delete(f"/api/investors/{code}")
    success(data=result["data"])
