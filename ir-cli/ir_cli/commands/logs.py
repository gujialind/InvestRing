"""日志管理命令组"""
import typer
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("login")
def login_logs(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """查看登录日志"""
    client = APIClient.from_config()
    result = client.get("/api/system/logs/login", params={"page": page, "page_size": page_size})
    success(data=result["data"], meta=result.get("meta"))


@app.command("audit")
def audit_logs(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """查看审计日志"""
    client = APIClient.from_config()
    result = client.get("/api/system/logs/audit", params={"page": page, "page_size": page_size})
    success(data=result["data"], meta=result.get("meta"))


@app.command("error")
def error_logs(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """查看错误日志"""
    client = APIClient.from_config()
    result = client.get("/api/system/logs/error", params={"page": page, "page_size": page_size})
    success(data=result["data"], meta=result.get("meta"))
