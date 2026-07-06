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
from app.services.trading_utils import get_next_trading_day

logger = logging.getLogger(__name__)


class NavNotAvailableError(Exception):
    """申请日组合快照不存在时抛出"""

    def __init__(self, portfolio_code: str, apply_date: date):
        self.portfolio_code = portfolio_code
        self.apply_date = apply_date
        super().__init__(
            f"申请日 {apply_date} 的组合 {portfolio_code} 净值快照不存在，请先生成快照"
        )


class InvalidStatusError(Exception):
    """状态不符合要求时抛出"""

    def __init__(self, message: str):
        super().__init__(message)


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
        shares = Decimal(str(subscription.amount)) / nav
        subscription.unit_price = nav
        subscription.shares = shares
    else:
        amount = Decimal(str(subscription.shares)) * nav
        subscription.unit_price = nav
        subscription.amount = amount

    # 5. 设置确认状态
    subscription.status = "confirmed"
    subscription.confirm_date = confirm_date

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
    auto_flush: bool = False,
) -> Subscription:
    """
    取消确认单笔申购/赎回的核心逻辑。

    将状态从 confirmed 回退至 pending，清空确认相关字段。

    Args:
        db: 数据库会话
        subscription: 待取消确认的记录（必须为 confirmed 状态）
        auto_flush: 是否在结束时自动 flush

    Returns:
        回退后的 subscription 对象

    Raises:
        InvalidStatusError: 状态不是 confirmed
    """
    if subscription.status != "confirmed":
        raise InvalidStatusError("仅 confirmed 状态可取消确认")

    subscription.status = "pending"
    subscription.confirm_date = None
    subscription.unit_price = None
    # 申购时 shares 由确认计算得出，回退后应清空让重新确认时再算
    if subscription.sub_type == "subscribe":
        subscription.shares = None
    else:
        # 赎回时 amount 由确认计算得出，回退后应清空
        subscription.amount = None

    if auto_flush:
        db.flush()

    logger.info(f"取消确认: id={subscription.id}")

    return subscription
