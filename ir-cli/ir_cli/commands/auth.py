"""认证管理命令组"""
import typer
from ir_cli import config
from ir_cli.client import APIClient
from ir_cli.output import EXIT_AUTH, success, error

app = typer.Typer(no_args_is_help=True)


@app.command("login")
def login(
    code: str = typer.Option(..., "--code", help="用户代码"),
    password: str = typer.Option(..., "--password", help="密码"),
):
    """登录获取 token"""
    base_url = config.get_base_url()
    client = APIClient(base_url)
    result = client.post("/api/auth/login", json_data={"code": code, "password": password})
    data = result["data"]
    # 存储 token
    config.save_token({
        "token": data["token"],
        "expires_at": data["expires_at"],
        "user": data["user"],
    })
    success(data={"user": data["user"], "expires_at": data["expires_at"]})


@app.command("logout")
def logout():
    """登出并清理本地 token"""
    client = APIClient.from_config(require_auth=True)
    client.post("/api/auth/logout")
    config.clear_token()
    success(data={"message": "登出成功"})


@app.command("change-password")
def change_password(
    old_password: str = typer.Option(..., "--old-password", help="旧密码"),
    new_password: str = typer.Option(..., "--new-password", help="新密码"),
):
    """修改密码"""
    client = APIClient.from_config()
    result = client.put("/api/auth/password", json_data={
        "old_password": old_password,
        "new_password": new_password,
    })
    success(data=result["data"])


@app.command("status")
def status():
    """显示当前用户和 token 状态（本地操作，不请求服务端）"""
    token_data = config.load_token()
    if not token_data:
        error("AUTH_REQUIRED", "未登录或 token 已过期，请执行: ir auth login", exit_code=EXIT_AUTH)
    base_url = config.get_base_url()
    success(data={
        "user": token_data.get("user"),
        "expires_at": token_data.get("expires_at"),
        "base_url": base_url,
    })
