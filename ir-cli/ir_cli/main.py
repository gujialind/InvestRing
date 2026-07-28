"""
InvestRing CLI - HTTP Client 入口

轻量 HTTP 客户端版 CLI，通过 REST API 与后端通信。
仅需 typer + httpx 两个依赖，可在任意设备上安装使用。
"""
from typing import Optional

import typer

_PROTOCOL_HELP = """InvestRing CLI - HTTP Client

输出协议: 成功 {"ok":true,"data":...,"meta"?,"hints"?} / 失败 {"ok":false,"error":{"code","message","hints"?}}

退出码: 0=成功 1=业务错误(可换参重试) 2=认证错误(ir auth login) 3=连接/超时

通用约定: --json 直传请求体 | --fields 裁剪输出 | --all 自动翻页 | --full 全字段 | --quiet 精简输出

执行 `ir schema` 一次性获取全部命令/参数/枚举/错误码的机读 JSON 结构。
"""

app = typer.Typer(
    name="ir",
    help=_PROTOCOL_HELP,
    no_args_is_help=True,
    rich_markup_mode=None,  # plain help 输出（无框线/ANSI），降低 AI agent token 消耗；子命令组继承此设置
)


def _version_callback(value: bool):
    if value:
        from importlib.metadata import PackageNotFoundError, version

        from ir_cli.output import success

        try:
            ver = version("investring-cli")
        except PackageNotFoundError:
            ver = "unknown"  # 未安装包直接源码运行时
        success(data={"name": "investring-cli", "version": ver})


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True,
        help="显示版本号并退出",
    ),
):
    pass


# 注册 18 个命令组
from ir_cli.commands import (
    auth,
    config_cmd,
    investors,
    portfolios,
    positions,
    subscriptions,
    trades,
    share_events,
    market_data,
    products,
    platforms,
    system,
    logs,
    tasks,
    snapshots,
    cash_transfers,
    sync_jobs,
    notifications,
)

app.add_typer(auth.app, name="auth", help="认证管理")
app.add_typer(config_cmd.app, name="config", help="本地配置管理")
app.add_typer(investors.app, name="investor", help="投资人管理")
app.add_typer(portfolios.app, name="portfolio", help="组合管理")
app.add_typer(positions.app, name="position", help="持仓管理")
app.add_typer(subscriptions.app, name="sub", help="申购赎回管理")
app.add_typer(trades.app, name="trade", help="调仓交易管理")
app.add_typer(share_events.app, name="share-event", help="份额变动事件管理")
app.add_typer(market_data.app, name="market", help="市场数据")
app.add_typer(products.app, name="product", help="产品管理")
app.add_typer(platforms.app, name="platform", help="平台管理")
app.add_typer(system.app, name="system", help="系统管理")
app.add_typer(logs.app, name="log", help="日志管理")
app.add_typer(tasks.app, name="task", help="任务管理")
app.add_typer(snapshots.app, name="snapshot", help="快照管理")
app.add_typer(cash_transfers.app, name="cash-transfer", help="现金转移管理")
app.add_typer(sync_jobs.app, name="sync-job", help="同步任务管理")
app.add_typer(notifications.app, name="notification", help="通知管理")


@app.command("schema")
def schema(
    group: Optional[str] = typer.Argument(None, help="仅输出指定命令组（如 trade）"),
    index: bool = typer.Option(
        False, "--index",
        help="仅输出极简命令索引（<1KB）；与命令组参数互斥，同时传报 VALIDATION_ERROR",
    ),
):
    """输出全 CLI 机读结构（命令/参数/枚举/错误码/输出协议/响应字段契约），供 AI agent 一次性了解全部指令"""
    from ir_cli.output import error, success
    from ir_cli.schema import build_schema, is_group

    if index and group:
        error("VALIDATION_ERROR", "--index 与命令组参数互斥：先 ir schema --index 拿索引，再 ir schema <group> 按组加载")
    root = typer.main.get_command(app)
    try:
        result = build_schema(root, group, index_only=index)
    except KeyError:
        groups = sorted(name for name, cmd in root.commands.items() if is_group(cmd))
        error("VALIDATION_ERROR", f"命令组 '{group}' 不存在，可用命令组: {', '.join(groups)}")
    success(data=result)
