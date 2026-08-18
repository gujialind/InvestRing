"""
申购赎回确认服务

将申购赎回确认/取消确认的核心业务逻辑从路由层提取，
供 HTTP API、CLI、快照重算自动确认等多处复用。
"""
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
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
from app.services.position_service import (
    calculate_investor_available_shares,
    compute_cash_balance,
)
from app.services.exceptions import BusinessError, NotFoundError
from app.utils.quantize import quantize_amount, quantize_shares

logger = logging.getLogger(__name__)


def _as_date(value):
    """归一为 date：portfolio.started_at 是 DateTime 列但承载日期语义，
    驱动读回类型不稳定（date/datetime），与 confirm_date 比较前先归一。"""
    return value.date() if hasattr(value, "date") and callable(value.date) else value


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
        BusinessError: CONFIRM_BEFORE_STARTED——申购确认日早于组合首笔到账日（issue #179 硬闸门）
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

    # 2.5 乱序补录硬闸门（issue #179）：申购确认日不得早于组合首笔到账日。
    # #180 不变量保证 started_at = 现存最小 confirm_date，闸门封死「后来者把
    # 到账日插到已按 1.0 定价申购的申请日之前」的污染空间。
    # confirm_date == started_at 放行（同日多平台申购生命线）；started_at 为空豁免。
    if subscription.sub_type == "subscribe" and portfolio and portfolio.started_at:
        if confirm_date < _as_date(portfolio.started_at):
            raise BusinessError(
                "CONFIRM_BEFORE_STARTED",
                f"申购确认日 {confirm_date} 早于组合首笔到账日 {portfolio.started_at}，"
                f"如需补录更早的申购，请先取消确认该首笔申购后依序重录",
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

    # 3. 净值三级决策（issue #179）
    snapshot = (
        db.query(PortfolioValueSnapshot)
        .filter(
            PortfolioValueSnapshot.portfolio_code == subscription.portfolio_code,
            PortfolioValueSnapshot.snapshot_date == subscription.apply_date,
        )
        .first()
    )
    if snapshot:
        nav = Decimal(str(snapshot.unit_price))
    else:
        # 初始窗口例外：申购是组合现金的唯一来源（CASH trade 受 CASH_TRADE_FORBIDDEN
        # 限制、现金转移只搬运存量、事件需先有持仓），故「不存在 confirm_date <=
        # apply_date 的 confirmed 申购」⟺ 申请日零持仓 ⟺ 净值结构性恒为 1.0000。
        # 动态计算，天然覆盖任意 confirm/unconfirm 顺序；赎回分支自然免疫
        # （有可用份额必存在更早到账的申购，此查询必然命中）。
        cash_arrived = (
            db.query(Subscription.id)
            .filter(
                Subscription.portfolio_code == subscription.portfolio_code,
                Subscription.sub_type == "subscribe",
                Subscription.status == "confirmed",
                Subscription.confirm_date <= subscription.apply_date,
            )
            .first()
        )
        if cash_arrived:
            raise NavNotAvailableError(
                subscription.portfolio_code, subscription.apply_date
            )
        nav = Decimal("1.0000")

    # 4. 计算份额/金额
    if subscription.sub_type == "subscribe":
        # 确认份额量化到 2 位（四舍五入）；金额为创建时已量化的用户输入（issue #94）
        shares = quantize_shares(Decimal(str(subscription.amount)) / nav)
        subscription.unit_price = nav
        subscription.shares = shares
    else:
        # 赎回金额量化到 2 位（issue #94）：shares(2位) × nav(4位) 四舍五入，
        # 误差计入基金财产，现金划出与平台 2 位口径一致
        amount = quantize_amount(Decimal(str(subscription.shares)) * nav)
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

    # 6. 首次申购激活组合（激活轮次与 started_at 是两个正交概念，issue #180）
    if is_first and subscription.sub_type == "subscribe" and portfolio and portfolio.status == "draft":
        portfolio.status = "active"
    # started_at = 现存最小 confirm_date（到账事实）：写入条件放宽为 started_at is
    # None（reactivate 空组合后新首购不漏设）；闸门保证后续申购 confirm_date >=
    # started_at，故首次写入的必然是最小值
    if subscription.sub_type == "subscribe" and portfolio and portfolio.started_at is None:
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
        BusinessError: 确认日及之后已有快照（SNAPSHOT_DEPENDENCY）；
            申购入金已被后续交易消耗（UNCONFIRM_WOULD_NEGATIVE_CASH，issue #180）
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

    # 负现金防护（issue #180 回滚链）：申购的 CASH buy 腿删除后，若该入金已被
    # 后续交易消耗将使平台现金为负——拒绝而非级联回滚下游（不隐式破坏已确认
    # 交易）。赎回的 CASH sell 腿只会加现金，无需校验。
    # 位于任何回退赋值之前，避免抛错后残留脏 ORM 状态。
    if subscription.sub_type == "subscribe":
        as_of = max(date.today(), subscription.confirm_date)
        balance = compute_cash_balance(
            db, subscription.portfolio_code, subscription.platform_code, as_of
        )
        if balance - Decimal(str(subscription.amount)) < 0:
            raise BusinessError(
                "UNCONFIRM_WOULD_NEGATIVE_CASH",
                f"取消确认将使平台 {subscription.platform_code} 现金为负"
                f"（该笔入金已被后续交易消耗），请先取消依赖该现金的交易",
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

    # 生产 session 为 autoflush=False（app/database.py）：上面的 status/confirm_date
    # 回退仍在 ORM 内存态，下面的 min 聚合直接走 SQL 会把本条仍算作 confirmed
    # （级联循环中前序兄弟记录同理），导致 started_at 重算脏读——查询前显式 flush。
    db.flush()

    # started_at 重算（issue #180）：started_at = 现存 confirmed 申购的最小
    # confirm_date（到账事实），无则 NULL。只查申购即可：「无 confirmed 申购 ⟹
    # 无 confirmed 赎回」（赎回需快照→持仓→申购，快照保护阻断反向删除）。
    # 状态回退仅 active→draft（closed 是用户意图态，级联删快照是数据修复副作用）。
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == subscription.portfolio_code)
        .first()
    )
    if portfolio:
        min_confirm = (
            db.query(func.min(Subscription.confirm_date))
            .filter(
                Subscription.portfolio_code == subscription.portfolio_code,
                Subscription.sub_type == "subscribe",
                Subscription.status == "confirmed",
            )
            .scalar()
        )
        portfolio.started_at = min_confirm
        if min_confirm is None and portfolio.status == "active":
            portfolio.status = "draft"

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
        # 用户输入金额先量化到 2 位（四舍五入）（issue #94）
        amount_d = quantize_amount(Decimal(str(amount)))
        if amount_d <= 0:
            raise BusinessError("INVALID_AMOUNT", "申购金额必须大于0")
        new_sub = Subscription(
            portfolio_code=portfolio_code, investor_code=investor_code,
            platform_code=platform_code, sub_type="subscribe",
            amount=amount_d, apply_date=apply_date,
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


def list_subscriptions(
    db: Session,
    *,
    portfolio_code: Optional[str] = None,
    investor_code: Optional[str] = None,
    status: Optional[str] = None,
    sub_type: Optional[str] = None,
    platform_code: Optional[str] = None,
    apply_date_start: Optional[date] = None,
    apply_date_end: Optional[date] = None,
    confirm_date_start: Optional[date] = None,
    confirm_date_end: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Subscription], int]:
    """申购赎回列表查询（服务端筛选 + 分页，issue #125）。

    - 日期区间均为闭区间；同组 start > end 抛 INVALID_DATE_RANGE（422）。
    - pending 记录的 confirm_date 为**预计确认日**（创建时按 T+1 设定、unconfirm
      时重算保持非空），确认日期区间筛选对 pending 命中预计值。
    - 排序：apply_date DESC, id DESC（同日期内新记录在前）。
    - viewer 限制由 router 叠加（非 admin 强制 investor_code=current_user.code），
      本函数不感知权限。

    Returns:
        (items, total)：当前页记录与过滤后总数（分页前）。
    """
    if apply_date_start and apply_date_end and apply_date_start > apply_date_end:
        raise BusinessError(
            "INVALID_DATE_RANGE",
            f"start_date ({apply_date_start}) 不能晚于 end_date ({apply_date_end})",
            http_status=422,
        )
    if confirm_date_start and confirm_date_end and confirm_date_start > confirm_date_end:
        raise BusinessError(
            "INVALID_DATE_RANGE",
            f"start_date ({confirm_date_start}) 不能晚于 end_date ({confirm_date_end})",
            http_status=422,
        )

    query = db.query(Subscription)
    if portfolio_code:
        query = query.filter(Subscription.portfolio_code == portfolio_code)
    if investor_code:
        query = query.filter(Subscription.investor_code == investor_code)
    if status:
        query = query.filter(Subscription.status == status)
    if sub_type:
        query = query.filter(Subscription.sub_type == sub_type)
    if platform_code:
        query = query.filter(Subscription.platform_code == platform_code)
    if apply_date_start:
        query = query.filter(Subscription.apply_date >= apply_date_start)
    if apply_date_end:
        query = query.filter(Subscription.apply_date <= apply_date_end)
    if confirm_date_start:
        query = query.filter(Subscription.confirm_date >= confirm_date_start)
    if confirm_date_end:
        query = query.filter(Subscription.confirm_date <= confirm_date_end)

    total = query.count()
    items = (
        query.order_by(Subscription.apply_date.desc(), Subscription.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total
