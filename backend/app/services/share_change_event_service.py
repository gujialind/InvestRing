"""
份额变动事件服务

将份额变动事件的校验、计算、确认拆分、取消/取消确认逻辑从路由层提取，
供 REST API、CLI、快照重算自动确认多处复用（消除 snapshot_service 反向依赖 router）。

service 层只抛领域异常（BusinessError/NotFoundError），不 import fastapi、不 commit。
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.share_change_event import ShareChangeEvent
from app.models.portfolio import Portfolio
from app.models.platform import Platform
from app.models.portfolio_position import PortfolioPosition
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.services.trading_utils import is_trading_day, get_latest_snapshot_date
from app.services.exceptions import BusinessError, NotFoundError
from app.utils.quantize import quantize_shares

logger = logging.getLogger(__name__)

FUND_LEVEL_TYPES = {"share_split", "share_merge", "bonus_share"}
PLATFORM_LEVEL_TYPES = {"cash_dividend", "reinvest_dividend", "forced_adjustment"}


def _compute_event_fields(event: ShareChangeEvent) -> None:
    """按 event_type 计算 shares_change/shares_after/cash_change。
    forced_adjustment 由用户直接填写，不自动计算（份额仅量化）。

    份额类字段统一量化到 2 位（四舍五入），且保证 shares_after 与
    shares_change 严格自洽：乘除产生新份额的类型（split/merge）先量化
    shares_after 再反算 shares_change；增量型（reinvest/bonus）先量化
    shares_change 再用 es + shares_change 重算 shares_after。
    cash_change 是金额，不量化。
    """
    es = event.entitlement_shares or Decimal("0")
    if event.event_type == "cash_dividend":
        event.cash_change = es * Decimal(str(event.div_cash or 0))
        event.shares_change = Decimal("0")
        event.shares_after = es
    elif event.event_type == "reinvest_dividend":
        event.shares_change = quantize_shares(
            es * Decimal(str(event.div_cash or 0)) / Decimal(str(event.reinvest_nav or 1))
        )
        event.shares_after = es + event.shares_change
        event.cash_change = Decimal("0")
    elif event.event_type == "share_split":
        event.shares_after = quantize_shares(es * Decimal(str(event.ratio or 1)))
        event.shares_change = event.shares_after - es
        event.cash_change = Decimal("0")
    elif event.event_type == "share_merge":
        event.shares_after = quantize_shares(es / Decimal(str(event.ratio or 1)))
        event.shares_change = event.shares_after - es
        event.cash_change = Decimal("0")
    elif event.event_type == "bonus_share":
        event.shares_change = quantize_shares(es * Decimal(str(event.ratio or 0)))
        event.shares_after = es + event.shares_change
        event.cash_change = Decimal("0")
    elif event.event_type == "forced_adjustment":
        # shares_change / cash_change 由用户直接填写；份额量化，金额不动
        if event.shares_change is not None:
            event.shares_change = quantize_shares(Decimal(str(event.shares_change)))


def check_platform_coverage(
    db: Session,
    *,
    portfolio_code: str,
    product_code: str,
    entitlement_date: date,
    ex_date: date,
    platform_code: Optional[str],
) -> List[str]:
    """检查同 ex_date 的平台级事件是否覆盖所有有持仓的平台。
    返回未覆盖的平台列表（空列表表示全覆盖）。
    """
    positions = db.query(PortfolioPosition.platform_code).filter(
        PortfolioPosition.portfolio_code == portfolio_code,
        PortfolioPosition.product_code == product_code,
        PortfolioPosition.snapshot_date == entitlement_date,
        PortfolioPosition.shares > 0,
    ).distinct().all()
    held_platforms = {p[0] for p in positions if p[0]}

    existing = db.query(ShareChangeEvent.platform_code).filter(
        ShareChangeEvent.portfolio_code == portfolio_code,
        ShareChangeEvent.product_code == product_code,
        ShareChangeEvent.ex_date == ex_date,
        ShareChangeEvent.status != "cancelled",
        ShareChangeEvent.platform_code.isnot(None),
    ).distinct().all()
    covered = {p[0] for p in existing if p[0]}
    if platform_code:
        covered.add(platform_code)

    return list(held_platforms - covered)


def _confirm_fund_level_event(db: Session, event: ShareChangeEvent) -> None:
    """基金级事件确认：自动拆分为各平台子记录。
    供 confirm_share_change_event 和 auto_confirm_after_snapshot 共用。
    """
    all_positions = db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_code == event.portfolio_code,
        PortfolioPosition.product_code == event.product_code,
        PortfolioPosition.snapshot_date == event.entitlement_date,
        PortfolioPosition.shares > 0,
    ).all()

    if not all_positions:
        raise ValueError("权益登记日无持仓，无需确认")

    total_shares = Decimal("0")
    now = datetime.now()
    # #37 savepoint：子记录拆分失败回滚 savepoint，不影响外层事务
    sp = db.connection().begin_nested()
    try:
        for pos in all_positions:
            platform_shares = Decimal(str(pos.shares or 0))
            total_shares += platform_shares
            child = ShareChangeEvent(
                portfolio_code=event.portfolio_code,
                product_code=event.product_code,
                market=event.market,
                event_type=event.event_type,
                ex_date=event.ex_date,
                entitlement_date=event.entitlement_date,
                platform_code=pos.platform_code,
                event_source=event.event_source,
                parent_event_id=event.id,
                entitlement_shares=platform_shares,
                shares_before=platform_shares,
                ratio=event.ratio,
                div_cash=event.div_cash,
                reinvest_nav=event.reinvest_nav,
                status="confirmed",
                confirmed_at=now,
            )
            _compute_event_fields(child)
            db.add(child)
        db.flush()
        sp.commit()
    except Exception:
        sp.rollback()
        raise

    # 父记录设汇总值
    event.entitlement_shares = total_shares
    event.shares_before = total_shares
    _compute_event_fields(event)
    event.status = "confirmed"
    event.confirmed_at = now


def _validate_event_dates(
    db: Session, portfolio_code: str, ex_date: date, entitlement_date: date
) -> None:
    """校验事件双日期：均为交易日、ex_date > entitlement_date、晚于最新快照日。

    创建与更新（pending 改日期）共用，保证两条路径校验一致。
    """
    # 权益登记日必须是交易日
    if not is_trading_day(db, entitlement_date):
        raise BusinessError("INVALID_ENTITLEMENT_DATE", "权益登记日不是交易日")
    # 除息日必须是交易日
    if not is_trading_day(db, ex_date):
        raise BusinessError("INVALID_EX_DATE", "除息日不是交易日")
    # 除息日必须严格大于权益登记日
    if ex_date <= entitlement_date:
        raise BusinessError(
            "INVALID_DATE_ORDER",
            "除息日必须严格大于权益登记日（ex_date > entitlement_date）",
        )
    # 除息日必须晚于最新快照日
    latest_snapshot = get_latest_snapshot_date(db, portfolio_code)
    if latest_snapshot and ex_date <= latest_snapshot:
        raise BusinessError(
            "DATE_BEFORE_SNAPSHOT",
            f"除息日必须晚于最新快照日（{latest_snapshot}）",
        )


def create_share_change_event(
    db: Session,
    *,
    portfolio_code: str,
    event_type: str,
    ex_date: date,
    entitlement_date: date,
    product_code: Optional[str] = None,
    market: Optional[str] = None,
    platform_code: Optional[str] = None,
    entitlement_shares: Optional[Decimal] = None,
    shares_before: Optional[Decimal] = None,
    shares_change: Optional[Decimal] = None,
    shares_after: Optional[Decimal] = None,
    cash_change: Optional[Decimal] = None,
    cash_product_code: Optional[str] = None,
    div_cash: Optional[Decimal] = None,
    reinvest_nav: Optional[Decimal] = None,
    ratio: Optional[Decimal] = None,
    event_source: str = "manual",
    tushare_event_id: Optional[str] = None,
    notes: Optional[str] = None,
    force_cover: bool = False,
) -> ShareChangeEvent:
    """创建份额变动事件（含全部校验与平台分级约束），供 REST 与 CLI 共用。不 commit。"""
    _validate_event_dates(db, portfolio_code, ex_date, entitlement_date)

    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise NotFoundError("NOT_FOUND", "组合不存在")

    # 分级校验：平台级必填 platform_code，基金级禁止指定
    if event_type in PLATFORM_LEVEL_TYPES:
        if not platform_code:
            raise BusinessError(
                "PLATFORM_REQUIRED",
                f"{event_type} 为平台级事件，必须指定 platform_code",
            )
        platform = db.query(Platform).filter(Platform.code == platform_code).first()
        if not platform:
            raise NotFoundError("PLATFORM_NOT_FOUND", f"平台 {platform_code} 不存在")
        # 全覆盖校验（默认阻断，force_cover 降为 warning）
        uncovered = check_platform_coverage(
            db, portfolio_code=portfolio_code, product_code=product_code,
            entitlement_date=entitlement_date, ex_date=ex_date, platform_code=platform_code,
        )
        if uncovered:
            if not force_cover:
                raise BusinessError(
                    "PLATFORM_NOT_COVERED",
                    f"平台覆盖不全，未覆盖平台: {uncovered}，可传 force_cover=true 降级为 warning",
                )
            logger.warning(f"平台覆盖不全（force_cover），未覆盖平台: {uncovered}")
    elif event_type in FUND_LEVEL_TYPES:
        if platform_code:
            raise BusinessError(
                "PLATFORM_NOT_ALLOWED",
                f"{event_type} 为基金级事件，不应指定 platform_code",
            )

    new_event = ShareChangeEvent(
        portfolio_code=portfolio_code,
        product_code=product_code,
        market=market,
        event_type=event_type,
        ex_date=ex_date,
        entitlement_date=entitlement_date,
        platform_code=platform_code,
        # 用户直填的份额类字段统一量化到 2 位（cash_change 是金额不量化）
        entitlement_shares=quantize_shares(entitlement_shares),
        shares_before=quantize_shares(shares_before),
        shares_change=quantize_shares(shares_change),
        shares_after=quantize_shares(shares_after),
        cash_change=cash_change,
        cash_product_code=cash_product_code,
        div_cash=div_cash,
        reinvest_nav=reinvest_nav,
        ratio=ratio,
        event_source=event_source,
        tushare_event_id=tushare_event_id,
        notes=notes,
        status="pending",
    )
    db.add(new_event)
    return new_event


def update_share_change_event(
    db: Session, event: ShareChangeEvent, updates: dict
) -> ShareChangeEvent:
    """更新份额变动事件（仅 pending 可改），供 REST 与 CLI 共用。不 commit。

    - confirmed 拒绝直改（含基金级子记录，子记录恒为 confirmed），
      须先 unconfirm，经快照保护（SNAPSHOT_DEPENDENCY）把关
    - 日期变更时用合并后生效值重跑创建时的双日期校验
    """
    if event.status == "confirmed":
        raise BusinessError(
            "CANNOT_MODIFY_CONFIRMED",
            "已确认的份额变动事件不可直接修改，请先取消确认后再修改",
        )

    if updates.keys() & {"ex_date", "entitlement_date"}:
        effective_ex_date = updates.get("ex_date", event.ex_date)
        effective_entitlement_date = updates.get(
            "entitlement_date", event.entitlement_date
        )
        _validate_event_dates(
            db, event.portfolio_code, effective_ex_date, effective_entitlement_date
        )

    for field, value in updates.items():
        setattr(event, field, value)
    return event


def confirm_share_change_event(db: Session, event: ShareChangeEvent) -> ShareChangeEvent:
    """确认份额变动事件（回写 entitlement_shares、计算、基金级自动拆分）。不 commit。"""
    if event.status != "pending":
        raise BusinessError("INVALID_STATUS", "仅 pending 状态可确认")

    # 校验权益登记日持仓快照是否存在
    position_snapshot = db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_code == event.portfolio_code,
        PortfolioPosition.snapshot_date == event.entitlement_date,
    ).first()
    if not position_snapshot:
        raise BusinessError("MISSING_POSITION_SNAPSHOT", "权益登记日持仓快照不存在")

    if event.platform_code is None:
        # 基金级事件：自动拆分为各平台子记录
        try:
            _confirm_fund_level_event(db, event)
        except ValueError as e:
            raise BusinessError("MISSING_POSITION_SNAPSHOT", str(e))
    else:
        # 平台级事件：按 platform_code 过滤读取 entitlement_shares
        entitlement_position = db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == event.portfolio_code,
            PortfolioPosition.product_code == event.product_code,
            PortfolioPosition.platform_code == event.platform_code,
            PortfolioPosition.snapshot_date == event.entitlement_date,
        ).first()
        entitlement_shares = (
            Decimal(str(entitlement_position.shares or 0)) if entitlement_position else Decimal("0")
        )
        event.entitlement_shares = entitlement_shares
        event.shares_before = entitlement_shares
        _compute_event_fields(event)
        event.status = "confirmed"
        event.confirmed_at = datetime.now()

    return event


def cancel_share_change_event(db: Session, event: ShareChangeEvent) -> ShareChangeEvent:
    """取消份额变动事件（仅 pending）。不 commit。"""
    if event.status != "pending":
        raise BusinessError("INVALID_STATUS", "仅 pending 状态可取消")
    event.status = "cancelled"
    return event


def unconfirm_share_change_event(db: Session, event: ShareChangeEvent) -> ShareChangeEvent:
    """取消确认份额变动事件（快照保护 + 子记录级联 + 清空计算字段）。不 commit。

    - 仅 confirmed 状态可 unconfirm
    - 子记录（parent_event_id 非空）单独 unconfirm 拒绝
    - ex_date 及之后已有快照则拒绝
    - 基金级父记录级联删除所有子记录
    """
    if event.status != "confirmed":
        raise BusinessError("INVALID_STATUS", "仅 confirmed 状态可取消确认")

    # 子记录不允许单独 unconfirm
    if event.parent_event_id is not None:
        raise BusinessError(
            "CANNOT_UNCONFIRM_CHILD",
            "基金级事件的子记录不允许单独取消确认，请对父记录执行 unconfirm",
        )

    # 快照保护：ex_date 及之后已有快照则拒绝
    snapshots_after = db.query(PortfolioValueSnapshot).filter(
        PortfolioValueSnapshot.portfolio_code == event.portfolio_code,
        PortfolioValueSnapshot.snapshot_date >= event.ex_date,
    ).count()
    if snapshots_after > 0:
        raise BusinessError(
            "SNAPSHOT_DEPENDENCY",
            f"该事件已被快照纳入（{event.ex_date} 及之后有 {snapshots_after} 张快照），"
            f"请先删除 {event.ex_date} 及之后的快照",
        )

    if event.platform_code is None:
        # 基金级父记录：级联删除所有子记录
        db.query(ShareChangeEvent).filter(
            ShareChangeEvent.parent_event_id == event.id
        ).delete(synchronize_session=False)

    # 置 pending 并清空确认时回写的计算字段
    event.status = "pending"
    event.confirmed_at = None
    event.shares_change = None
    event.shares_after = None
    event.cash_change = None
    event.entitlement_shares = None
    event.shares_before = None

    return event
