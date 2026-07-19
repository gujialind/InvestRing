"""
调仓交易确认服务

将 Trade 确认的核心业务逻辑（净值获取、份额/金额重算、配对 CASH 腿同步）
从路由层提取，供 HTTP API 手动确认与快照重算 auto_confirm 多处复用。
"""
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.trade import Trade
from app.models.product import Product
from app.models.price_record import PriceRecord
from app.services.trading_utils import get_next_trading_day

logger = logging.getLogger(__name__)


def get_nav_for_trade_confirmation(
    db: Session, product_code: str, market: str, trade_date: date, is_qdii: bool
) -> Optional[Decimal]:
    """
    获取调仓交易确认时的净值

    规则：
    - QDII产品：必须使用T日净值，禁止向前查找
    - 非QDII净值型产品：必须使用T日净值，禁止向前查找

    Args:
        db: 数据库会话
        product_code: 产品代码
        market: 市场类型
        trade_date: 交易日期（T日）
        is_qdii: 是否为QDII产品

    Returns:
        净值（Decimal），如果不存在则返回 None（由调用方决定是否拒绝）

    Raises:
        HTTPException: QDII产品T日净值不存在时抛出异常
    """
    if is_qdii:
        # QDII：必须取T日净值，禁止向前查找
        price_record = db.query(PriceRecord).filter(
            PriceRecord.product_code == product_code,
            PriceRecord.market == market,
            PriceRecord.date == trade_date
        ).first()

        if not price_record or not price_record.unit_price:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "MISSING_QDII_NAV",
                    "message": f"QDII产品{product_code}在T={trade_date}的净值尚未同步，请等待T+2日后重试或手动指定净值"
                }
            )

        return Decimal(str(price_record.unit_price))
    else:
        # 非QDII：必须取T日净值，禁止向前查找（对齐文档"禁止向前查找"）
        price_record = db.query(PriceRecord).filter(
            PriceRecord.product_code == product_code,
            PriceRecord.market == market,
            PriceRecord.date == trade_date
        ).first()

        if price_record and price_record.unit_price:
            return Decimal(str(price_record.unit_price))

        return None


def sync_transfer_group(
    db: Session, trade: Trade, target_status: str, confirm_date: Optional[date] = None
):
    """同步 transfer_group 关联的另一腿状态"""
    if not trade.transfer_group:
        return
    paired = db.query(Trade).filter(
        Trade.transfer_group == trade.transfer_group,
        Trade.id != trade.id,
    ).all()
    # #37 savepoint：配对腿更新失败回滚 savepoint，不影响外层事务
    # 用连接级 SAVEPOINT（db.connection().begin_nested()）而非 session 级
    # db.begin_nested()，避免触发 after_transaction_end 事件与测试隔离监听器冲突
    sp = db.connection().begin_nested()
    try:
        for paired_trade in paired:
            paired_trade.status = target_status
            if confirm_date is not None:
                paired_trade.confirm_date = confirm_date
            elif target_status == "pending":
                # unconfirm 时需要重新计算期望确认日
                paired_product = db.query(Product).filter(
                    Product.code == paired_trade.product_code,
                    Product.market == paired_trade.market,
                ).first()
                if paired_product:
                    paired_confirm_days = paired_product.confirm_days or 0
                    paired_trade.confirm_date = get_next_trading_day(
                        db, paired_trade.trade_date, days=paired_confirm_days
                    )
        db.flush()  # 确保 ORM 变更在 savepoint 内写入 DB
        sp.commit()
    except Exception:
        sp.rollback()
        raise


def confirm_single_trade(
    db: Session,
    trade: Trade,
    product: Optional[Product],
    *,
    confirm_date: Optional[date] = None,
    price: Optional[Decimal] = None,
) -> Trade:
    """
    确认单笔调仓交易的核心逻辑，供手动确认与 auto_confirm 共用。

    - confirm_date 已在创建时设定；若传入参数则覆盖（补录场景）
    - 净值型产品（OEF/LOF 且 CN_OTC）确认时获取 T 日净值并重算 shares/amount；
      QDII 严格取 T 日净值，缺失时抛 HTTPException
    - 场内产品不取净值（使用创建时的收盘价/手动价）
    - 置 status=confirmed 并原子同步配对 CASH 腿

    Args:
        db: 数据库会话
        trade: 待确认交易（须为 pending）
        product: 交易对应产品（CASH/未知产品可为 None，跳过净值逻辑）
        confirm_date: 覆盖确认日（补录场景）
        price: 手动指定价格（优先于系统净值）

    Returns:
        确认后的 trade 对象（未 commit，事务由调用方控制）
    """
    # confirm_date 已在创建时设定；若传入参数则覆盖（补录场景）
    if confirm_date is not None:
        trade.confirm_date = confirm_date

    # 净值型产品必须获取净值进行计算（场外基金）
    is_nav_product = (
        bool(product)
        and product.product_type in ["OEF", "LOF"]
        and trade.market == "CN_OTC"
    )

    if is_nav_product:
        # 净值型产品：获取T日净值（QDII会抛出异常如果净值不存在）
        nav_price = get_nav_for_trade_confirmation(
            db, trade.product_code, trade.market, trade.trade_date, product.is_qdii
        )

        # 非QDII产品可能返回None
        if nav_price is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "MISSING_NAV",
                    "message": f"产品{trade.product_code}在T={trade.trade_date}的净值尚未同步，无法确认交易"
                }
            )

        # 如果传入了价格，使用传入的价格；否则使用系统获取的净值
        final_price = Decimal(str(price)) if price is not None else nav_price

        trade.price = final_price
        if trade.trade_type == "buy":
            amount = Decimal(str(trade.actual_amount)) - Decimal(str(trade.fee))
            trade.shares = amount / final_price
            trade.amount = amount
        else:
            amount = Decimal(str(trade.shares)) * final_price
            trade.actual_amount = amount - Decimal(str(trade.fee))
            trade.amount = amount
    elif price is not None:
        # 非净值型产品但传入了价格（如手动指定）
        trade.price = Decimal(str(price))
        if trade.trade_type == "buy":
            amount = Decimal(str(trade.actual_amount)) - Decimal(str(trade.fee))
            trade.shares = amount / Decimal(str(price))
            trade.amount = amount
        else:
            amount = Decimal(str(trade.shares)) * Decimal(str(price))
            trade.actual_amount = amount - Decimal(str(trade.fee))
            trade.amount = amount

    trade.status = "confirmed"
    # 同步 transfer_group 配对腿（如基金调仓的配对 CASH 腿）
    sync_transfer_group(db, trade, "confirmed", trade.confirm_date)

    logger.info(
        f"交易确认: trade_id={trade.id}, type={trade.trade_type}, "
        f"product={trade.product_code}, confirm_date={trade.confirm_date}"
    )

    return trade
