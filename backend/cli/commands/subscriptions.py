"""
ir sub - 申购赎回命令组
"""
import typer
from typing import Optional
from datetime import date
from decimal import Decimal

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta, parse_date

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_subscriptions(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code"),
    investor_code: Optional[str] = typer.Option(None, "--investor-code"),
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
    all: bool = typer.Option(False, "--all"),
):
    """获取申购赎回列表"""
    with cli_context() as db:
        from app.models.subscription import Subscription

        query = db.query(Subscription).order_by(Subscription.created_at.desc())
        if portfolio_code:
            query = query.filter(Subscription.portfolio_code == portfolio_code)
        if investor_code:
            query = query.filter(Subscription.investor_code == investor_code)
        items, total, page, page_size = paginate(query, page, page_size, all)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("create")
def create_subscription(
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
    investor_code: str = typer.Option(..., "--investor-code"),
    sub_type: str = typer.Option(..., "--type", help="subscribe/redeem"),
    amount: Optional[float] = typer.Option(None, "--amount", help="申购金额"),
    shares: Optional[float] = typer.Option(None, "--shares", help="赎回份额"),
    apply_date: str = typer.Option(..., "--apply-date", help="YYYY-MM-DD"),
    notes: Optional[str] = typer.Option(None, "--notes"),
):
    """创建申购/赎回"""
    with cli_context() as db:
        from app.models.subscription import Subscription
        from app.models.portfolio import Portfolio
        from app.models.investor import Investor
        from app.services.trading_utils import is_trading_day
        from app.services.position_service import calculate_investor_available_shares

        ad = parse_date(apply_date)
        if not is_trading_day(db, ad):
            error("NON_TRADING_DAY", "非交易日，请等待交易日再提交")

        portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
        if not portfolio:
            error("NOT_FOUND", "组合不存在")
        if portfolio.status not in ("active", "draft"):
            error("PORTFOLIO_NOT_ACTIVE", "组合未激活")

        investor = db.query(Investor).filter(Investor.code == investor_code).first()
        if not investor:
            error("NOT_FOUND", "投资人不存在")

        if sub_type == "subscribe":
            if not amount or amount <= 0:
                error("INVALID_AMOUNT", "申购金额必须大于0")
            new_sub = Subscription(
                portfolio_code=portfolio_code, investor_code=investor_code,
                sub_type="subscribe", amount=Decimal(str(amount)),
                apply_date=ad, status="pending", notes=notes,
            )
        elif sub_type == "redeem":
            if not shares or shares <= 0:
                error("INVALID_SHARES", "赎回份额必须大于0")
            available = calculate_investor_available_shares(db, portfolio_code, investor_code)
            if Decimal(str(shares)) > available:
                error("INSUFFICIENT_SHARES", f"赎回份额超过可用份额({float(available)})")
            new_sub = Subscription(
                portfolio_code=portfolio_code, investor_code=investor_code,
                sub_type="redeem", shares=Decimal(str(shares)),
                apply_date=ad, status="pending", notes=notes,
            )
        else:
            error("INVALID_TYPE", "类型必须为 subscribe 或 redeem")

        db.add(new_sub)
        db.flush()
        db.refresh(new_sub)
        success(data=serialize_model(new_sub))


@app.command("get")
def get_subscription(
    id: int = typer.Argument(...),
):
    """查看申购赎回详情"""
    with cli_context() as db:
        from app.models.subscription import Subscription

        sub = db.query(Subscription).filter(Subscription.id == id).first()
        if not sub:
            error("NOT_FOUND", f"申购赎回记录 {id} 不存在")
        success(data=serialize_model(sub))


@app.command("confirm")
def confirm_subscription(
    id: int = typer.Argument(...),
):
    """确认申购赎回（首次申购净值固定1.0000，确认日期和净值均由后端自动计算）"""
    with cli_context() as db:
        from app.models.subscription import Subscription
        from app.services.subscription_service import (
            confirm_single_subscription,
            NavNotAvailableError,
            InvalidStatusError,
        )

        sub = db.query(Subscription).filter(Subscription.id == id).first()
        if not sub:
            error("NOT_FOUND", f"申购赎回记录 {id} 不存在")

        try:
            confirm_single_subscription(db, sub)
        except InvalidStatusError as e:
            error("INVALID_STATUS", str(e))
        except NavNotAvailableError as e:
            error("NAV_NOT_AVAILABLE", str(e))

        db.flush()
        db.refresh(sub)
        success(data={
            "message": "申购赎回确认成功",
            "subscription": serialize_model(sub),
        })


@app.command("cancel")
def cancel_subscription(
    id: int = typer.Argument(...),
):
    """取消申购赎回（仅 pending 状态）"""
    with cli_context() as db:
        from app.models.subscription import Subscription

        sub = db.query(Subscription).filter(Subscription.id == id).first()
        if not sub:
            error("NOT_FOUND", f"申购赎回记录 {id} 不存在")
        if sub.status != "pending":
            error("INVALID_STATUS", "仅 pending 状态可取消")
        sub.status = "cancelled"
        db.flush()
        success(data={"message": "申购赎回已取消", "id": id})


@app.command("unconfirm")
def unconfirm_subscription(
    id: int = typer.Argument(...),
):
    """取消确认（confirmed -> pending）"""
    with cli_context() as db:
        from app.models.subscription import Subscription
        from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
        from app.services.subscription_service import (
            unconfirm_single_subscription,
            InvalidStatusError,
        )

        sub = db.query(Subscription).filter(Subscription.id == id).first()
        if not sub:
            error("NOT_FOUND", f"申购赎回记录 {id} 不存在")

        # 快照保护
        if sub.status == "confirmed" and sub.confirm_date:
            snapshots_after = (
                db.query(PortfolioValueSnapshot)
                .filter(
                    PortfolioValueSnapshot.portfolio_code == sub.portfolio_code,
                    PortfolioValueSnapshot.snapshot_date >= sub.confirm_date,
                )
                .count()
            )
            if snapshots_after > 0:
                error(
                    "SNAPSHOT_DEPENDENCY",
                    f"该申赎已被快照纳入（{sub.confirm_date} 及之后有 {snapshots_after} 张快照），"
                    f"请先删除 {sub.confirm_date} 及之后的快照",
                )

        try:
            unconfirm_single_subscription(db, sub)
        except InvalidStatusError as e:
            error("INVALID_STATUS", str(e))

        db.flush()
        success(data={"message": "申购赎回已取消确认", "id": id})
