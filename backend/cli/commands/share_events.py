"""
ir share-event - 份额变动事件命令组
"""
import typer
from typing import Optional
from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta, parse_date

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_events(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code"),
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
    all: bool = typer.Option(False, "--all"),
):
    """获取份额变动事件列表"""
    with cli_context() as db:
        from app.models.share_change_event import ShareChangeEvent

        query = db.query(ShareChangeEvent).order_by(ShareChangeEvent.created_at.desc())
        if portfolio_code:
            query = query.filter(ShareChangeEvent.portfolio_code == portfolio_code)
        items, total, page, page_size = paginate(query, page, page_size, all)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("create")
def create_event(
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
    product_code: str = typer.Option(..., "--product-code"),
    market: str = typer.Option(..., "--market"),
    event_type: str = typer.Option(..., "--event-type",
        help="cash_dividend/reinvest_dividend/share_split/share_merge/bonus_share/forced_adjustment"),
    event_date: str = typer.Option(..., "--event-date", help="YYYY-MM-DD"),
    entitlement_date: str = typer.Option(..., "--entitlement-date", help="YYYY-MM-DD"),
    entitlement_shares: Optional[float] = typer.Option(None, "--entitlement-shares"),
    shares_before: Optional[float] = typer.Option(None, "--shares-before"),
    shares_change: Optional[float] = typer.Option(None, "--shares-change"),
    shares_after: Optional[float] = typer.Option(None, "--shares-after"),
    ratio: Optional[float] = typer.Option(None, "--ratio"),
    div_cash: Optional[float] = typer.Option(None, "--div-cash"),
    reinvest_nav: Optional[float] = typer.Option(None, "--reinvest-nav"),
    cash_change: Optional[float] = typer.Option(None, "--cash-change"),
    event_source: Optional[str] = typer.Option(None, "--event-source"),
    notes: Optional[str] = typer.Option(None, "--notes"),
):
    """创建份额变动事件（权益登记日必须是交易日）"""
    with cli_context() as db:
        from decimal import Decimal
        from app.models.share_change_event import ShareChangeEvent
        from app.models.portfolio import Portfolio
        from app.services.trading_utils import is_trading_day

        event_date = parse_date(event_date)
        entitlement_date = parse_date(entitlement_date)

        if not is_trading_day(db, entitlement_date):
            error("INVALID_ENTITLEMENT_DATE", "权益登记日不是交易日")

        portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
        if not portfolio:
            error("NOT_FOUND", "组合不存在")

        def to_d(v):
            return Decimal(str(v)) if v is not None else None

        event = ShareChangeEvent(
            portfolio_code=portfolio_code, product_code=product_code, market=market,
            event_type=event_type, event_date=event_date, entitlement_date=entitlement_date,
            entitlement_shares=to_d(entitlement_shares),
            shares_before=to_d(shares_before), shares_change=to_d(shares_change),
            shares_after=to_d(shares_after), ratio=to_d(ratio),
            div_cash=to_d(div_cash), reinvest_nav=to_d(reinvest_nav),
            cash_change=to_d(cash_change),
            event_source=event_source, notes=notes, status="pending",
        )
        db.add(event)
        db.flush()
        db.refresh(event)
        success(data=serialize_model(event))


@app.command("get")
def get_event(
    id: int = typer.Argument(...),
):
    """查看份额变动事件详情"""
    with cli_context() as db:
        from app.models.share_change_event import ShareChangeEvent

        event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
        if not event:
            error("NOT_FOUND", f"事件 {id} 不存在")
        success(data=serialize_model(event))


@app.command("update")
def update_event(
    id: int = typer.Argument(...),
    event_date: Optional[str] = typer.Option(None, "--event-date", help="YYYY-MM-DD"),
    entitlement_shares: Optional[float] = typer.Option(None, "--entitlement-shares"),
    ratio: Optional[float] = typer.Option(None, "--ratio"),
    div_cash: Optional[float] = typer.Option(None, "--div-cash"),
    reinvest_nav: Optional[float] = typer.Option(None, "--reinvest-nav"),
    cash_change: Optional[float] = typer.Option(None, "--cash-change"),
    notes: Optional[str] = typer.Option(None, "--notes"),
):
    """更新份额变动事件"""
    with cli_context() as db:
        from decimal import Decimal
        from app.models.share_change_event import ShareChangeEvent

        event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
        if not event:
            error("NOT_FOUND", f"事件 {id} 不存在")

        def to_d(v):
            return Decimal(str(v)) if v is not None else None

        if event_date is not None:
            event.event_date = parse_date(event_date)
        if entitlement_shares is not None:
            event.entitlement_shares = to_d(entitlement_shares)
        if ratio is not None:
            event.ratio = to_d(ratio)
        if div_cash is not None:
            event.div_cash = to_d(div_cash)
        if reinvest_nav is not None:
            event.reinvest_nav = to_d(reinvest_nav)
        if cash_change is not None:
            event.cash_change = to_d(cash_change)
        if notes is not None:
            event.notes = notes

        db.flush()
        db.refresh(event)
        success(data=serialize_model(event))


@app.command("delete")
def delete_event(
    id: int = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes"),
):
    """删除份额变动事件"""
    with cli_context() as db:
        from app.models.share_change_event import ShareChangeEvent

        event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
        if not event:
            error("NOT_FOUND", f"事件 {id} 不存在")
        db.delete(event)
        db.flush()
        success(data={"message": f"事件 {id} 已删除"})


@app.command("confirm")
def confirm_event(
    id: int = typer.Argument(...),
):
    """确认份额变动事件（校验权益登记日持仓快照存在）"""
    with cli_context() as db:
        from app.models.share_change_event import ShareChangeEvent
        from app.models.portfolio_position import PortfolioPosition

        event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
        if not event:
            error("NOT_FOUND", f"事件 {id} 不存在")
        if event.status != "pending":
            error("INVALID_STATUS", "仅 pending 状态可确认")

        snapshot = db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == event.portfolio_code,
            PortfolioPosition.snapshot_date == event.entitlement_date,
        ).first()
        if not snapshot:
            error("MISSING_POSITION_SNAPSHOT", "权益登记日持仓快照不存在")

        event.status = "confirmed"
        db.flush()
        db.refresh(event)
        success(data={"message": "事件确认成功", "event": serialize_model(event)})


@app.command("cancel")
def cancel_event(
    id: int = typer.Argument(...),
):
    """取消份额变动事件（仅 pending 状态）"""
    with cli_context() as db:
        from app.models.share_change_event import ShareChangeEvent

        event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
        if not event:
            error("NOT_FOUND", f"事件 {id} 不存在")
        if event.status != "pending":
            error("INVALID_STATUS", "仅 pending 状态可取消")
        event.status = "cancelled"
        db.flush()
        success(data={"message": "事件已取消", "id": id})
