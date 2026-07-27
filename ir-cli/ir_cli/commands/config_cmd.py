"""配置管理命令组（纯本地操作，读写 ~/.ir/config）"""
import typer
from ir_cli import config
from ir_cli.output import success, error

app = typer.Typer(no_args_is_help=True)

# 允许的配置键及说明（防止拼写错误写入无效键）
ALLOWED_KEYS = {
    "base_url": "服务端地址（优先级低于 IR_BASE_URL 环境变量）",
}


@app.command("set")
def set_config(
    key: str = typer.Argument(..., help=f"配置键，可选: {', '.join(ALLOWED_KEYS)}"),
    value: str = typer.Argument(..., help="配置值"),
):
    """写入配置项到 ~/.ir/config"""
    if key not in ALLOWED_KEYS:
        error(
            "VALIDATION_ERROR",
            f"不支持的配置键 '{key}'，可选: {', '.join(ALLOWED_KEYS)}",
        )
    if key == "base_url":
        value = value.rstrip("/")
        if not value.startswith(("http://", "https://")):
            error("VALIDATION_ERROR", "base_url 必须以 http:// 或 https:// 开头")
    config.save_config(key, value)
    success(data={key: value}, hints=["执行 ir config show 查看生效配置"])


@app.command("show")
def show_config():
    """显示当前生效配置（含环境变量覆盖后的实际值）"""
    file_config = config.load_config()
    success(data={
        "config_file": str(config.get_ir_dir() / "config"),
        "file_config": file_config,
        "effective": {
            "base_url": config.get_base_url(),  # 已合并 IR_BASE_URL 覆盖
        },
    })
