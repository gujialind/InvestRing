"""
ir share-event - 份额变动事件命令组
"""
import typer
from typing import Optional
from decimal import Decimal
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
    ex_date: str = typer.Option(..., "--ex-date", help="YYYY-MM-DD"),
    entitlement_date: str = typer.Option(..., "--entitlement-date", help="YYYY-MM-DD"),
    platform_code: Optional[str] = typer.Option(None, "--platform-code", help="平台级事件必填"),
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
    force_cover: bool = typer.Option(False, "--force-cover", help="平台覆盖不全时降为 warning"),
):
    """创建份额变动事件（校验/平台分级约束由服务层统一处理）

    \b
    示例:
      ir share-event create --portfolio-code PORT001 --product-code 022959.OF --market CN_OTC --event-type cash_dividend --ex-date 2026-06-05 --entitlement-date 2026-06-04 --platform-code ALIPAY --entitlement-shares 10000 --div-cash 0.05
    """
    with cli_context() as db:
        from app.services.share_change_event_service import (
            create_share_change_event as create_event_service,
        )

        def to_d(v):
            return Decimal(str(v)) if v is not None else None

        event = create_event_service(
            db,
            portfolio_code=portfolio_code,
            event_type=event_type,
            ex_date=parse_date(ex_date),
            entitlement_date=parse_date(entitlement_date),
            product_code=product_code,
            market=market,
            platform_code=platform_code,
            entitlement_shares=to_d(entitlement_shares),
            shares_before=to_d(shares_before),
            shares_change=to_d(shares_change),
            shares_after=to_d(shares_after),
            ratio=to_d(ratio),
            div_cash=to_d(div_cash),
            reinvest_nav=to_d(reinvest_nav),
            cash_change=to_d(cash_change),
            event_source=event_source or "manual",
            notes=notes,
            force_cover=force_cover,
        )
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
    ex_date: Optional[str] = typer.Option(None, "--ex-date", help="YYYY-MM-DD"),
    entitlement_shares: Optional[float] = typer.Option(None, "--entitlement-shares"),
    ratio: Optional[float] = typer.Option(None, "--ratio"),
    div_cash: Optional[float] = typer.Option(None, "--div-cash"),
    reinvest_nav: Optional[float] = typer.Option(None, "--reinvest-nav"),
    cash_change: Optional[float] = typer.Option(None, "--cash-change"),
    notes: Optional[str] = typer.Option(None, "--notes"),
):
    """更新份额变动事件（仅 pending 可改，confirmed 需先 unconfirm）"""
    with cli_context() as db:
        from app.models.share_change_event import ShareChangeEvent
        from app.services.share_change_event_service import (
            update_share_change_event as update_event_service,
        )

        event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
        if not event:
            error("NOT_FOUND", f"事件 {id} 不存在")

        def to_d(v):
            return Decimal(str(v)) if v is not None else None

        updates = {}
        if ex_date is not None:
            updates["ex_date"] = parse_date(ex_date)
        if entitlement_shares is not None:
            updates["entitlement_shares"] = to_d(entitlement_shares)
        if ratio is not None:
            updates["ratio"] = to_d(ratio)
        if div_cash is not None:
            updates["div_cash"] = to_d(div_cash)
        if reinvest_nav is not None:
            updates["reinvest_nav"] = to_d(reinvest_nav)
        if cash_change is not None:
            updates["cash_change"] = to_d(cash_change)
        if notes is not None:
            updates["notes"] = notes

        # confirmed 阻断、日期重校验均在 service 单点实现（REST/CLI 共用）
        update_event_service(db, event, updates)

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
        # 父记录：先删除所有子记录
        db.query(ShareChangeEvent).filter(
            ShareChangeEvent.parent_event_id == event.id
        ).delete(synchronize_session=False)
        db.delete(event)
        db.flush()
        success(data={"message": f"事件 {id} 已删除"})


@app.command("confirm")
def confirm_event(
    id: int = typer.Argument(...),
):
    """确认份额变动事件（计算/基金级自动拆分由服务层统一处理）"""
    with cli_context() as db:
        from app.models.share_change_event import ShareChangeEvent
        from app.services.share_change_event_service import (
            confirm_share_change_event as confirm_event_service,
        )

        event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
        if not event:
            error("NOT_FOUND", f"事件 {id} 不存在")
        confirm_event_service(db, event)
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
        from app.services.share_change_event_service import (
            cancel_share_change_event as cancel_event_service,
        )

        event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
        if not event:
            error("NOT_FOUND", f"事件 {id} 不存在")
        cancel_event_service(db, event)
        db.flush()
        success(data={"message": "事件已取消", "id": id})


@app.command("unconfirm")
def unconfirm_event(
    id: int = typer.Argument(...),
):
    """取消确认份额变动事件（快照保护 + 子记录级联 + 清空计算字段）"""
    with cli_context() as db:
        from app.models.share_change_event import ShareChangeEvent
        from app.services.share_change_event_service import (
            unconfirm_share_change_event as unconfirm_event_service,
        )

        event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
        if not event:
            error("NOT_FOUND", f"事件 {id} 不存在")
        unconfirm_event_service(db, event)
        db.flush()
        db.refresh(event)
        success(data={"message": "事件已取消确认", "event": serialize_model(event)})
