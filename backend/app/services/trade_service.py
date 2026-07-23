"""
调仓交易确认服务

将 Trade 确认的核心业务逻辑（净值获取、份额/金额重算、配对 CASH 腿同步）
从路由层提取，供 HTTP API 手动确认与快照重算 auto_confirm 多处复用。
"""
import logging
import uuid
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
    db: Session, product_code: str, market: str, trade_date: date
) -> Optional[Decimal]:
    """
    获取调仓交易确认时的净值

    规则：
    - 场外基金统一取 T 日（成交当日）净值，禁止向前查找，不区分 QDII/非 QDII。
      QDII 与非 QDII 的差异仅在确认间隔（T+2 / T+1），已通过创建时设定的
      confirm_date 体现；到确认日净值理应可取，缺失则由调用方拒绝确认。

    Args:
        db: 数据库会话
        product_code: 产品代码
        market: 市场类型
        trade_date: 交易日期（T日）

    Returns:
        净值（Decimal），如果不存在则返回 None（由调用方决定是否拒绝）
    """
    price_record = db.query(PriceRecord).filter(
        PriceRecord.product_code == product_code,
        PriceRecord.market == market,
        PriceRecord.date == trade_date
    ).first()

    if price_record and price_record.unit_price:
        return Decimal(str(price_record.unit_price))

    return None


def attach_paired_cash_leg(
    db: Session,
    fund_trade: Trade,
    cash_amount: Decimal,
    confirm_date: Optional[date],
    status: str = "pending",
) -> Trade:
    """为基金腿生成 transfer_group 并构造/加入配对 CASH 腿。

    cash_amount 采用 router 语义 = 基金腿 actual_amount（买入=支出含费，卖出=收入）。
    供 REST router 与后端 CLI 共用，确保基金买/卖必配 CASH 腿。

    Returns:
        新建的 CASH 腿（已 db.add，未 commit）
    """
    group = f"rebal_{uuid.uuid4().hex[:12]}"
    fund_trade.transfer_group = group
    cash_trade = Trade(
        portfolio_code=fund_trade.portfolio_code,
        platform_code=fund_trade.platform_code,
        product_code="CASH",
        market="",
        trade_type="sell" if fund_trade.trade_type == "buy" else "buy",
        shares=None,
        amount=cash_amount,
        price=Decimal("1"),
        fee=Decimal("0"),
        actual_amount=cash_amount,
        trade_date=fund_trade.trade_date,
        confirm_date=confirm_date,
        status=status,
        transfer_group=group,
    )
    db.add(cash_trade)
    return cash_trade


def sync_transfer_group(
    db: Session, trade: Trade, target_status: str, confirm_date: Optional[date] = None
):
    """同步 transfer_group 关联的另一腿状态与金额

    - 传播 `target_status` 与 `confirm_date`（unconfirm 时重算期望确认日）
    - 若源腿为基金腿（product_code != "CASH"），将其 actual_amount 镜像给配对
      CASH 腿（CASH 腿金额恒等于基金腿 actual_amount）。确认时净值型基金
      actual_amount 可能被重算，需同步；金额未变时为幂等写入
    """
    if not trade.transfer_group:
        return
    paired = db.query(Trade).filter(
        Trade.transfer_group == trade.transfer_group,
        Trade.id != trade.id,
    ).all()
    # CASH 腿金额 = 基金腿 actual_amount（买入=支出、卖出=收入）；
    # 仅当源腿为基金腿时向 CASH 腿镜像，避免 CASH→CASH / CASH→基金误写
    mirror_amount = None
    if trade.product_code != "CASH":
        mirror_amount = trade.actual_amount if trade.actual_amount is not None else trade.amount
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
            # 同步配对 CASH 腿金额（确认时净值重算后需同步）
            if mirror_amount is not None and paired_trade.product_code == "CASH":
                paired_trade.amount = mirror_amount
                paired_trade.actual_amount = mirror_amount
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
    - 场外基金（OEF/LOF 且 CN_OTC）确认时统一获取 T 日（成交当日）净值并重算 shares/amount，
      不区分 QDII/非 QDII，一律以净值计算；缺失 T 日净值时抛 MISSING_NAV 拒绝确认
    - 场外基金若传入 price 仅作一致性校验：须与 T 日净值相等，否则抛 PRICE_NAV_MISMATCH，
      手动价不覆盖净值（不传则直接取净值）
    - 场内基金不取净值，使用创建时录入的成交价（成交价录入时必填，见 trades.py 创建校验）
    - 置 status=confirmed 并原子同步配对 CASH 腿

    Args:
        db: 数据库会话
        trade: 待确认交易（须为 pending）
        product: 交易对应产品（CASH/未知产品可为 None，跳过净值逻辑）
        confirm_date: 覆盖确认日（补录场景）
        price: 手动价格；场外基金仅用于与 T 日净值一致性校验（不覆盖净值），
            场内基金作为覆盖成交价

    Returns:
        确认后的 trade 对象（未 commit，事务由调用方控制）
    """
    # confirm_date 已在创建时设定；若传入参数则覆盖（补录场景）
    if confirm_date is not None:
        trade.confirm_date = confirm_date

    # 场外净值型基金（CN_OTC 的 OEF/LOF）确认时必须获取 T 日净值进行计算
    is_otc_nav_fund = (
        bool(product)
        and product.product_type in ["OEF", "LOF"]
        and trade.market == "CN_OTC"
    )

    if is_otc_nav_fund:
        # 净值型产品：获取T日净值
        nav_price = get_nav_for_trade_confirmation(
            db, trade.product_code, trade.market, trade.trade_date
        )

        # 净值不存在，无法确认交易
        if nav_price is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "MISSING_NAV",
                    "message": f"产品{trade.product_code}在T={trade.trade_date}的净值尚未同步，无法确认交易"
                }
            )

        # 手动价格为可选校验项：传入时必须与 T 日净值一致，否则拒绝确认由用户修正；
        # 场外基金一律以 T 日净值计算，手动价不参与计算、也不覆盖净值
        if price is not None:
            input_price = Decimal(str(price)).quantize(Decimal("0.0001"))
            if input_price != nav_price.quantize(Decimal("0.0001")):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "PRICE_NAV_MISMATCH",
                        "message": f"传入价格({input_price})与T={trade.trade_date}净值({nav_price})不一致，请核对后修改，或不传价格直接取净值"
                    }
                )

        final_price = nav_price

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
        # 场内基金/其他非净值型：仅在传入价格时按传入成交价重算（补录/手动覆盖场景）
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
