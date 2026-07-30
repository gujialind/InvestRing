"""
申购赎回确认服务

将申购赎回确认/取消确认的核心业务逻辑从路由层提取，
供 HTTP API、CLI、快照重算自动确认等多处复用。
"""
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.models.portfolio import Portfolio
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.models.trade import Trade
from app.models.investor import Investor
from app.models.platform import Platform
from app.services.trading_utils import (
    get_next_trading_day,
    is_trading_day,
    get_latest_snapshot_date,
)
from app.services.position_service import calculate_investor_available_shares
from app.services.exceptions import BusinessError, NotFoundError
from app.utils.quantize import quantize_shares

logger = logging.getLogger(__name__)


class NavNotAvailableError(BusinessError):
    """申请日组合快照不存在时抛出（映射 NAV_NOT_AVAILABLE）"""

    def __init__(self, portfolio_code: str, apply_date: date):
        self.portfolio_code = portfolio_code
        self.apply_date = apply_date
        super().__init__(
            "NAV_NOT_AVAILABLE",
            f"申请日 {apply_date} 的组合 {portfolio_code} 净值快照不存在，请先生成快照",
        )


class InvalidStatusError(BusinessError):
    """状态不符合要求时抛出（映射 INVALID_STATUS）"""

    def __init__(self, message: str):
        super().__init__("INVALID_STATUS", message)


def confirm_single_subscription(
    db: Session,
    subscription: Subscription,
    *,
    auto_flush: bool = False,
) -> Subscription:
    """
    确认单笔申购/赎回的核心逻辑。

    - 确认日期由后端自动计算（T+1）
    - 净值自动确定（首次申购固定1.0000，否则取申请日组合快照净值）
    - 首次申购确认后自动激活组合状态

    Args:
        db: 数据库会话
        subscription: 待确认的申购/赎回记录（必须为 pending 状态）
        auto_flush: 是否在结束时自动 flush（默认为 False，由调用者控制事务）

    Returns:
        确认后的 subscription 对象

    Raises:
        InvalidStatusError: 状态不是 pending
        NavNotAvailableError: 申请日快照不存在
    """
    if subscription.status != "pending":
        raise InvalidStatusError("仅 pending 状态可确认")

    # 1. 确认日期：T+1（申请日的下一个交易日）
    confirm_date = get_next_trading_day(db, subscription.apply_date, days=1)

    # 2. 判断是否为首次申购
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == subscription.portfolio_code)
        .first()
    )

    is_first = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == subscription.portfolio_code,
            Subscription.sub_type == "subscribe",
            Subscription.status == "confirmed",
        )
        .count()
        == 0
    )

    # 3. 净值确定
    if is_first:
        nav = Decimal("1.0000")
    else:
        snapshot = (
            db.query(PortfolioValueSnapshot)
            .filter(
                PortfolioValueSnapshot.portfolio_code == subscription.portfolio_code,
                PortfolioValueSnapshot.snapshot_date == subscription.apply_date,
            )
            .first()
        )
        if not snapshot:
            raise NavNotAvailableError(
                subscription.portfolio_code, subscription.apply_date
            )
        nav = Decimal(str(snapshot.unit_price))

    # 4. 计算份额/金额
    if subscription.sub_type == "subscribe":
        # 确认份额量化到 2 位（四舍五入）；净值与金额保持原精度
        shares = quantize_shares(Decimal(str(subscription.amount)) / nav)
        subscription.unit_price = nav
        subscription.shares = shares
    else:
        amount = Decimal(str(subscription.shares)) * nav
        subscription.unit_price = nav
        subscription.amount = amount

    # 5. 设置确认状态
    subscription.status = "confirmed"
    subscription.confirm_date = confirm_date

    # 5.5 生成配对 CASH trade（显式记录现金变动）
    cash_trade = Trade(
        portfolio_code=subscription.portfolio_code,
        platform_code=subscription.platform_code,
        product_code="CASH",
        market="",
        trade_type="buy" if subscription.sub_type == "subscribe" else "sell",
        amount=Decimal(str(subscription.amount)),
        price=Decimal("1"),
        fee=Decimal("0"),
        actual_amount=Decimal(str(subscription.amount)),
        trade_date=subscription.apply_date,
        confirm_date=confirm_date,
        status="confirmed",
        transfer_group=f"sub_{subscription.id}",
    )
    db.add(cash_trade)

    # 6. 首次申购激活组合
    if is_first and subscription.sub_type == "subscribe" and portfolio and portfolio.status == "draft":
        portfolio.status = "active"
        portfolio.started_at = confirm_date

    if auto_flush:
        db.flush()

    logger.info(
        f"申购确认: id={subscription.id}, type={subscription.sub_type}, "
        f"nav={nav}, confirm_date={confirm_date}"
    )

    return subscription


def unconfirm_single_subscription(
    db: Session,
    subscription: Subscription,
    *,
    check_snapshot: bool = True,
    auto_flush: bool = False,
) -> Subscription:
    """
    取消确认单笔申购/赎回的核心逻辑。

    将状态从 confirmed 回退至 pending，清空确认相关字段。

    Args:
        db: 数据库会话
        subscription: 待取消确认的记录（必须为 confirmed 状态）
        check_snapshot: 是否执行快照保护（默认 True）。用户触发的 unconfirm
            应保持 True；快照删除级联回退（_cascade_unconfirm_subscriptions）
            须显式传 False——此时快照正在被删除，不应被本检查阻断。
        auto_flush: 是否在结束时自动 flush

    Returns:
        回退后的 subscription 对象

    Raises:
        InvalidStatusError: 状态不是 confirmed
        BusinessError: 确认日及之后已有快照（SNAPSHOT_DEPENDENCY）
    """
    if subscription.status != "confirmed":
        raise InvalidStatusError("仅 confirmed 状态可取消确认")

    # 快照保护：确认日及之后已有快照则拒绝（级联删除快照时 check_snapshot=False 跳过）
    if check_snapshot and subscription.confirm_date:
        snapshots_after = (
            db.query(PortfolioValueSnapshot)
            .filter(
                PortfolioValueSnapshot.portfolio_code == subscription.portfolio_code,
                PortfolioValueSnapshot.snapshot_date >= subscription.confirm_date,
            )
            .count()
        )
        if snapshots_after > 0:
            raise BusinessError(
                "SNAPSHOT_DEPENDENCY",
                f"该申赎已被快照纳入（{subscription.confirm_date} 及之后有 {snapshots_after} 张快照），"
                f"请先删除 {subscription.confirm_date} 及之后的快照",
            )

    subscription.status = "pending"
    # 重算期望确认日（申赎恒 T+1）而非置 None，保持 pending 记录 confirm_date 非空，
    # 避免快照校验 confirm_date <= target 因 SQL NULL 比较漏检（与 unconfirm_trade 对齐）
    subscription.confirm_date = get_next_trading_day(db, subscription.apply_date, days=1)
    subscription.unit_price = None
    # 申购时 shares 由确认计算得出，回退后应清空让重新确认时再算
    if subscription.sub_type == "subscribe":
        subscription.shares = None
    else:
        # 赎回时 amount 由确认计算得出，回退后应清空
        subscription.amount = None

    # 物理删除配对 CASH trade（派生记录，生命周期跟随 subscription）
    db.query(Trade).filter(
        Trade.transfer_group == f"sub_{subscription.id}"
    ).delete(synchronize_session=False)

    if auto_flush:
        db.flush()

    logger.info(f"取消确认: id={subscription.id}")

    return subscription


def create_subscription(
    db: Session,
    *,
    portfolio_code: str,
    investor_code: str,
    platform_code: str,
    sub_type: str,
    apply_date: date,
    amount: Optional[Decimal] = None,
    shares: Optional[Decimal] = None,
    notes: Optional[str] = None,
) -> Subscription:
    """创建申购/赎回（含全部校验），供 REST 与 CLI 共用。

    创建时即设定 confirm_date=T+1（与 REST 口径一致）。不 commit。
    """
    if not is_trading_day(db, apply_date):
        raise BusinessError("NON_TRADING_DAY", "非交易日，请等待交易日再提交")

    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise NotFoundError("NOT_FOUND", "组合不存在")
    # 首次申购时组合状态为 draft，确认后变为 active
    if portfolio.status not in ("active", "draft"):
        raise BusinessError("PORTFOLIO_NOT_ACTIVE", "组合未激活")

    # 申请日必须晚于最新快照日
    latest_snapshot_date = get_latest_snapshot_date(db, portfolio_code)
    if latest_snapshot_date and apply_date <= latest_snapshot_date:
        raise BusinessError(
            "DATE_BEFORE_SNAPSHOT",
            f"申请日必须晚于最新快照日（{latest_snapshot_date}）",
        )

    investor = db.query(Investor).filter(Investor.code == investor_code).first()
    if not investor:
        raise NotFoundError("NOT_FOUND", "投资人不存在")

    platform = db.query(Platform).filter(Platform.code == platform_code).first()
    if not platform:
        raise NotFoundError("PLATFORM_NOT_FOUND", f"平台 {platform_code} 不存在")

    confirm_date = get_next_trading_day(db, apply_date, days=1)

    if sub_type == "subscribe":
        if amount is None or Decimal(str(amount)) <= 0:
            raise BusinessError("INVALID_AMOUNT", "申购金额必须大于0")
        new_sub = Subscription(
            portfolio_code=portfolio_code, investor_code=investor_code,
            platform_code=platform_code, sub_type="subscribe",
            amount=Decimal(str(amount)), apply_date=apply_date,
            confirm_date=confirm_date, status="pending", notes=notes,
        )
    elif sub_type == "redeem":
        if shares is None or Decimal(str(shares)) <= 0:
            raise BusinessError("INVALID_SHARES", "赎回份额必须大于0")
        # 用户输入份额先量化到 2 位（四舍五入），再做精确比较
        shares_d = quantize_shares(Decimal(str(shares)))
        if shares_d <= 0:
            raise BusinessError("INVALID_SHARES", "赎回份额必须大于0")
        available = calculate_investor_available_shares(
            db, portfolio_code, investor_code, as_of_date=apply_date
        )
        if shares_d > available:
            raise BusinessError("INSUFFICIENT_SHARES", "赎回份额超过可用份额")
        new_sub = Subscription(
            portfolio_code=portfolio_code, investor_code=investor_code,
            platform_code=platform_code, sub_type="redeem",
            shares=shares_d, apply_date=apply_date,
            confirm_date=confirm_date, status="pending", notes=notes,
        )
    else:
        raise BusinessError("INVALID_TYPE", "类型必须为 subscribe 或 redeem")

    db.add(new_sub)
    return new_sub
