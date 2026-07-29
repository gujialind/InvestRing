"""
持仓相关服务函数

从 routers 层提取的共享函数，供 CLI 和 router 共用。
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.manual_market_value import ManualMarketValue
from app.models.portfolio_position import PortfolioPosition
from app.models.share_change_event import ShareChangeEvent
from app.models.subscription import Subscription
from app.models.trade import Trade
from app.models.portfolio import Portfolio
from app.models.platform import Platform
from app.services.trading_utils import (
    get_latest_snapshot_date,
    get_latest_snapshot_date_le,
    is_trading_day,
)
from app.services.exceptions import BusinessError, NotFoundError


def compute_cash_balance(
    db: Session,
    portfolio_code: str,
    platform_code: Optional[str] = None,
    as_of_date: Optional[date] = None,
) -> Decimal:
    """
    显式计算 as_of_date 时的现金余额。

    源1：trade 表 confirmed CASH trades（confirm_date <= as_of_date）
    源2：event 表 confirmed events（ex_date <= as_of_date, cash_change != 0）

    不含 manual_market_value 覆盖。用于：
    - 无快照时 calculate_available_cash 的降级基线
    - cash-position 端点审计字段（computed_value）
    快照生成走 _generate_portfolio_position 增量累加路径，不调用此函数。
    有快照时 calculate_available_cash 直接读 portfolio_position 快照表，亦不调用此函数。
    """
    if as_of_date is None:
        as_of_date = date.today()

    balance = Decimal("0")

    # 源1：CASH trades
    trades = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.product_code == "CASH",
        Trade.status == "confirmed",
        Trade.confirm_date <= as_of_date,
    )
    if platform_code:
        trades = trades.filter(Trade.platform_code == platform_code)

    for t in trades.all():
        if t.trade_type == "buy":
            balance += Decimal(str(t.amount or 0))
        elif t.trade_type == "sell":
            balance -= Decimal(str(t.amount or 0))

    # 源2：事件 cash_change
    events = db.query(ShareChangeEvent).filter(
        ShareChangeEvent.portfolio_code == portfolio_code,
        ShareChangeEvent.status == "confirmed",
        ShareChangeEvent.ex_date <= as_of_date,
        ShareChangeEvent.cash_change.isnot(None),
        ShareChangeEvent.cash_change != 0,
    )
    if platform_code:
        events = events.filter(ShareChangeEvent.platform_code == platform_code)

    for e in events.all():
        balance += Decimal(str(e.cash_change))

    return balance


def get_cash_value(
    db: Session,
    portfolio_code: str,
    platform_code: Optional[str],
    target_date: Optional[date],
) -> Decimal:
    """
    获取指定日期的现金值（含 manual_market_value 绝对替换）。

    基础 = compute_cash_balance(target_date)
    若存在 manual_market_value 覆盖（value_date == target_date），则绝对替换。

    target_date 为 None 时：compute_cash_balance 降级为 today，
    且跳过 manual 覆盖查询（无快照日可匹配）。

    注意：calculate_available_cash 已改为直接读快照表基线（#52），
    本函数保留用于 cash-position 端点审计展示等辅助场景。
    """
    v = compute_cash_balance(db, portfolio_code, platform_code, target_date)
    if target_date is not None:
        manual = db.query(ManualMarketValue).filter(
            ManualMarketValue.portfolio_code == portfolio_code,
            ManualMarketValue.platform_code == platform_code,
            ManualMarketValue.product_code == "CASH",
            ManualMarketValue.value_date == target_date,
        ).first()
        if manual:
            v = Decimal(str(manual.market_value))
    return v


def calculate_available_cash(
    db: Session,
    portfolio_code: str,
    platform_code: Optional[str] = None,
    as_of_date: Optional[date] = None,
) -> Decimal:
    """
    组合可用现金实时计算（显式流水版）。

    基线 = 最新快照日 portfolio_position 快照表中 CASH 行的 cash_amount
    （与 _generate_portfolio_position 增量范式口径一致，manual_market_value
    覆盖已 baked in 快照，自然继承；无快照时降级为 compute_cash_balance 全量流水）
    + 快照后 confirmed CASH buys（流入）
    − 快照后 confirmed CASH sells（流出）
    − pending CASH sells（已承诺未执行）
    + 快照后 confirmed event cash_change

    时点口径（#70/#78）：CASH 流出（sell）的资金承诺锚定**下单日 trade_date**，
    不论 pending/confirmed——confirmed sell 的 as_of 上限按 trade_date（而非
    confirm_date）判定，pending sell 仅在 trade_date <= as_of_date 时计提，
    消除 pending→confirmed 翻转后"预留隐身"；CASH 流入（buy）仍须 confirmed
    且 confirm_date <= as_of_date 才计入。

    as_of_date 为 None 时取当前最新快照日为基线、快照后范围不设上限
    （confirmed buy/sell 均计入，pending sell 全额计提，与历史口径一致）；
    传入时基线取 <= as_of_date 的最新快照日，confirmed buys 计
    confirm_date ∈ (latest_date, as_of_date]，confirmed sells 计
    confirm_date > latest_date 且 trade_date <= as_of_date，
    pending sells 计 trade_date <= as_of_date。
    """
    if as_of_date is not None:
        latest_date = get_latest_snapshot_date_le(db, portfolio_code, as_of_date)
    else:
        latest_date = get_latest_snapshot_date(db, portfolio_code)

    # 基线：直接读快照表 CASH 持仓（与 _generate_portfolio_position 增量范式口径一致，
    # manual_market_value 覆盖已 baked in 快照，自然继承）
    if latest_date is not None:
        cash_query = db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == portfolio_code,
            PortfolioPosition.product_code == "CASH",
            PortfolioPosition.snapshot_date == latest_date,
        )
        if platform_code:
            cash_query = cash_query.filter(PortfolioPosition.platform_code == platform_code)
        cash = sum(
            Decimal(str(p.cash_amount or 0)) for p in cash_query.all()
        )
    else:
        cash = compute_cash_balance(db, portfolio_code, platform_code, as_of_date)

    if latest_date is None:
        latest_date = date(1970, 1, 1)  # 确保 > 条件对所有 trade 生效

    # 快照后 confirmed CASH buys（流入：confirm_date <= as_of_date 才计入）
    after_buys = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.product_code == "CASH",
        Trade.status == "confirmed",
        Trade.trade_type == "buy",
        Trade.confirm_date > latest_date,
    )
    if as_of_date is not None:
        after_buys = after_buys.filter(Trade.confirm_date <= as_of_date)
    if platform_code:
        after_buys = after_buys.filter(Trade.platform_code == platform_code)

    for t in after_buys.all():
        cash += Decimal(str(t.amount or 0))

    # 快照后 confirmed CASH sells（流出：承诺锚定下单日，上限按 trade_date 判定）
    after_sells = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.product_code == "CASH",
        Trade.status == "confirmed",
        Trade.trade_type == "sell",
        Trade.confirm_date > latest_date,
    )
    if as_of_date is not None:
        after_sells = after_sells.filter(Trade.trade_date <= as_of_date)
    if platform_code:
        after_sells = after_sells.filter(Trade.platform_code == platform_code)

    for t in after_sells.all():
        cash -= Decimal(str(t.amount or 0))

    # pending CASH sells（已承诺未执行，需预留；as_of 时点仅计提已下单的）
    pending_sells = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.product_code == "CASH",
        Trade.status == "pending",
        Trade.trade_type == "sell",
    )
    if as_of_date is not None:
        pending_sells = pending_sells.filter(Trade.trade_date <= as_of_date)
    if platform_code:
        pending_sells = pending_sells.filter(Trade.platform_code == platform_code)

    for t in pending_sells.all():
        cash -= Decimal(str(t.amount or 0))

    # 快照后 confirmed event cash_change
    after_events = db.query(ShareChangeEvent).filter(
        ShareChangeEvent.portfolio_code == portfolio_code,
        ShareChangeEvent.status == "confirmed",
        ShareChangeEvent.ex_date > latest_date,
        ShareChangeEvent.cash_change.isnot(None),
        ShareChangeEvent.cash_change != 0,
    )
    if as_of_date is not None:
        after_events = after_events.filter(ShareChangeEvent.ex_date <= as_of_date)
    if platform_code:
        after_events = after_events.filter(ShareChangeEvent.platform_code == platform_code)

    for e in after_events.all():
        cash += Decimal(str(e.cash_change))

    return cash


def calculate_available_shares(
    db: Session,
    portfolio_code: str,
    product_code: str,
    market: Optional[str] = None,
    as_of_date: Optional[date] = None,
) -> Decimal:
    """
    基金可用份额实时计算：
    基金可用份额 = 最新快照份额
                - SUM(pending卖出份额)
                - SUM(confirmed卖出份额 WHERE 快照未生成)

    as_of_date 为 None 时基线取当前最新快照日；传入时取 <= as_of_date 的最新快照日，
    confirmed 卖出仅计 confirm_date 在 (latest_date, as_of_date] 的。
    """
    if as_of_date is not None:
        latest_date = get_latest_snapshot_date_le(db, portfolio_code, as_of_date)
    else:
        latest_date = get_latest_snapshot_date(db, portfolio_code)

    query = db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_code == portfolio_code,
        PortfolioPosition.product_code == product_code,
    )
    if market:
        query = query.filter(PortfolioPosition.market == market)
    if as_of_date is not None:
        query = query.filter(PortfolioPosition.snapshot_date <= as_of_date)
    latest_position = query.order_by(PortfolioPosition.snapshot_date.desc()).first()

    shares = Decimal(latest_position.shares) if latest_position and latest_position.shares else Decimal("0")

    pending_sells = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.product_code == product_code,
            Trade.status == "pending",
            Trade.trade_type == "sell",
        )
        .all()
    )
    for t in pending_sells:
        shares -= Decimal(t.shares) if t.shares else Decimal("0")

    confirmed_sells = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.product_code == product_code,
            Trade.status == "confirmed",
            Trade.trade_type == "sell",
        )
        .all()
    )
    for t in confirmed_sells:
        if latest_date is None or (
            t.confirm_date and t.confirm_date > latest_date
            and (as_of_date is None or t.confirm_date <= as_of_date)
        ):
            shares -= Decimal(t.shares) if t.shares else Decimal("0")

    return shares


def calculate_investor_available_shares(
    db: Session,
    portfolio_code: str,
    investor_code: str,
    as_of_date: Optional[date] = None,
) -> Decimal:
    """
    投资人可用份额实时计算：
    投资人可用份额 = 最新快照份额
                  - SUM(pending赎回份额)
                  - SUM(confirmed赎回份额 WHERE 快照未生成)

    as_of_date 为 None 时基线取当前最新快照日；传入时取 <= as_of_date 的最新快照日，
    confirmed 赎回仅计 confirm_date 在 (latest_date, as_of_date] 的。
    """
    from app.models.investor_holding import InvestorHolding

    if as_of_date is not None:
        latest_date = get_latest_snapshot_date_le(db, portfolio_code, as_of_date)
    else:
        latest_date = get_latest_snapshot_date(db, portfolio_code)

    holding_query = db.query(InvestorHolding).filter(
        InvestorHolding.portfolio_code == portfolio_code,
        InvestorHolding.investor_code == investor_code,
    )
    if as_of_date is not None:
        holding_query = holding_query.filter(InvestorHolding.snapshot_date <= as_of_date)
    latest_holding = holding_query.order_by(InvestorHolding.snapshot_date.desc()).first()
    shares = Decimal(latest_holding.shares) if latest_holding else Decimal("0")

    pending_redeems = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.investor_code == investor_code,
            Subscription.sub_type == "redeem",
            Subscription.status == "pending",
        )
        .all()
    )
    for s in pending_redeems:
        shares -= Decimal(s.shares) if s.shares else Decimal("0")

    confirmed_redeems = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.investor_code == investor_code,
            Subscription.sub_type == "redeem",
            Subscription.status == "confirmed",
        )
        .all()
    )
    for s in confirmed_redeems:
        if latest_date is None or (
            s.confirm_date and s.confirm_date > latest_date
            and (as_of_date is None or s.confirm_date <= as_of_date)
        ):
            shares -= Decimal(s.shares) if s.shares else Decimal("0")

    return shares


def update_cash_position(
    db: Session,
    *,
    portfolio_code: str,
    platform_code: str,
    amount: Decimal,
    update_date: Optional[date] = None,
    created_by: Optional[str] = None,
) -> dict:
    """现金市值修正：写 manual_market_value（绝对替换），供 REST 与 CLI 共用。

    绝不直接写 portfolio_position（快照表受 ORM 事件保护）。
    写入后需重新生成快照才会反映到持仓。不 commit。

    Returns:
        dict：portfolio_code/platform_code/cash_amount/computed_value/update_date(date)
    """
    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise NotFoundError("PORTFOLIO_NOT_FOUND", f"组合 {portfolio_code} 不存在")

    platform = db.query(Platform).filter(Platform.code == platform_code).first()
    if not platform:
        raise NotFoundError("PLATFORM_NOT_FOUND", f"平台 {platform_code} 不存在")

    target_date = update_date or date.today()
    if not is_trading_day(db, target_date):
        raise BusinessError("NON_TRADING_DAY", "非交易日，请等待交易日再提交")

    # 计算当前隐式值（用于审计）
    computed = compute_cash_balance(db, portfolio_code, platform_code, target_date)

    manual = db.query(ManualMarketValue).filter(
        ManualMarketValue.portfolio_code == portfolio_code,
        ManualMarketValue.platform_code == platform_code,
        ManualMarketValue.product_code == "CASH",
        ManualMarketValue.value_date == target_date,
    ).first()
    if manual:
        manual.market_value = Decimal(str(amount))
        manual.computed_value = computed
    else:
        manual = ManualMarketValue(
            portfolio_code=portfolio_code,
            platform_code=platform_code,
            product_code="CASH",
            value_date=target_date,
            market_value=Decimal(str(amount)),
            computed_value=computed,
            created_by=created_by,
        )
        db.add(manual)
    db.flush()

    return {
        "portfolio_code": portfolio_code,
        "platform_code": platform_code,
        "cash_amount": float(manual.market_value),
        "computed_value": float(computed) if computed is not None else None,
        "update_date": target_date,
    }
