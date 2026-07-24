"""
InvestRing CLI - HTTP Client 入口

轻量 HTTP 客户端版 CLI，通过 REST API 与后端通信。
仅需 typer + httpx 两个依赖，可在任意设备上安装使用。
"""
import typer

app = typer.Typer(
    name="ir",
    help="InvestRing CLI - HTTP Client",
    no_args_is_help=True,
)

# 注册 17 个命令组
from ir_cli.commands import (
    auth,
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
