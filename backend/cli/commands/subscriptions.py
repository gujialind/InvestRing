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
    platform_code: str = typer.Option(..., "--platform-code", help="交易平台代码"),
    sub_type: str = typer.Option(..., "--type", help="subscribe/redeem"),
    amount: Optional[float] = typer.Option(None, "--amount", help="申购金额"),
    shares: Optional[float] = typer.Option(None, "--shares", help="赎回份额"),
    apply_date: str = typer.Option(..., "--apply-date", help="YYYY-MM-DD"),
    notes: Optional[str] = typer.Option(None, "--notes"),
):
    """创建申购/赎回（校验由服务层统一处理）"""
    with cli_context() as db:
        from app.services.subscription_service import create_subscription as create_subscription_service

        new_sub = create_subscription_service(
            db,
            portfolio_code=portfolio_code,
            investor_code=investor_code,
            platform_code=platform_code,
            sub_type=sub_type,
            apply_date=parse_date(apply_date),
            amount=Decimal(str(amount)) if amount is not None else None,
            shares=Decimal(str(shares)) if shares is not None else None,
            notes=notes,
        )
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
        from app.services.subscription_service import confirm_single_subscription

        sub = db.query(Subscription).filter(Subscription.id == id).first()
        if not sub:
            error("NOT_FOUND", f"申购赎回记录 {id} 不存在")

        confirm_single_subscription(db, sub)

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
        from app.services.subscription_service import unconfirm_single_subscription

        sub = db.query(Subscription).filter(Subscription.id == id).first()
        if not sub:
            error("NOT_FOUND", f"申购赎回记录 {id} 不存在")

        unconfirm_single_subscription(db, sub)

        db.flush()
        success(data={"message": "申购赎回已取消确认", "id": id})
