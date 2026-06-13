from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from decimal import Decimal
from app.database import get_db
from app.models.trade import Trade
from app.models.portfolio import Portfolio
from app.models.product import Product
from app.models.portfolio_position import PortfolioPosition
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.models.trading_calendar import TradingCalendar
from app.models.price_record import PriceRecord
from app.schemas.trade import TradeCreate, TradeUpdate, TradeResponse
from app.dependencies import get_current_user, get_current_admin


def _get_next_trading_day(db: Session, from_date: date, days: int = 1) -> date:
    from sqlalchemy import func
    next_date = from_date
    for _ in range(max(days, 0)):
        next_date = (
            db.query(func.min(TradingCalendar.date))
            .filter(
                TradingCalendar.date > next_date,
                TradingCalendar.is_open == True,
            )
            .scalar()
        )
        if not next_date:
            break
    return next_date or from_date


def _prev_trading_day(db: Session, from_date: date, days: int = 1) -> date:
    """获取前 N 个交易日"""
    from sqlalchemy import func
    prev_date = from_date
    for _ in range(max(days, 0)):
        prev_date = (
            db.query(func.max(TradingCalendar.date))
            .filter(
                TradingCalendar.date < prev_date,
                TradingCalendar.is_open == True,
            )
            .scalar()
        )
        if not prev_date:
            break
    return prev_date or from_date


def _get_nav_for_trade_confirmation(
    db: Session, product_code: str, market: str, trade_date: date, is_qdii: bool
) -> Optional[Decimal]:
    """
    获取调仓交易确认时的净值
    
    规则：
    - QDII产品：必须使用T日净值，禁止向前查找
    - 非QDII净值型产品：使用T日或最近交易日净值
    
    Args:
        db: 数据库会话
        product_code: 产品代码
        market: 市场类型
        trade_date: 交易日期（T日）
        is_qdii: 是否为QDII产品
        
    Returns:
        净值（Decimal），如果不存在则返回 None
        
    Raises:
        HTTPException: QDII产品T日净值不存在时抛出异常
    """
    if is_qdii:
        # QDII：必须取T日净值，禁止向前查找
        price_record = db.query(PriceRecord).filter(
            PriceRecord.product_code == product_code,
            PriceRecord.market == market,
            PriceRecord.price_date == trade_date
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
        # 非QDII：取T日或最近的净值
        price_record = db.query(PriceRecord).filter(
            PriceRecord.product_code == product_code,
            PriceRecord.market == market,
            PriceRecord.price_date <= trade_date
        ).order_by(PriceRecord.price_date.desc()).first()
        
        if price_record and price_record.unit_price:
            return Decimal(str(price_record.unit_price))
        
        return None


router = APIRouter()


def _is_trading_day(db: Session, target_date: date) -> bool:
    cal = db.query(TradingCalendar).filter(TradingCalendar.date == target_date).first()
    if not cal:
        return False
    return cal.is_open


def _get_latest_snapshot_date(db: Session, portfolio_code: str) -> Optional[date]:
    from sqlalchemy import func
    result = (
        db.query(func.max(PortfolioValueSnapshot.snapshot_date))
        .filter(PortfolioValueSnapshot.portfolio_code == portfolio_code)
        .scalar()
    )
    return result


def _calculate_available_cash(db: Session, portfolio_code: str) -> Decimal:
    """
    组合可用现金实时计算：
    最新快照现金
    + SUM(confirmed申购金额 WHERE 快照未生成)
    - SUM(confirmed赎回金额 WHERE 快照未生成)
    - SUM(pending买入金额)
    - SUM(confirmed买入金额 WHERE 快照未生成)
    + SUM(confirmed卖出金额 WHERE 快照未生成)
    """
    latest_date = _get_latest_snapshot_date(db, portfolio_code)

    cash_position = (
        db.query(PortfolioPosition)
        .filter(
            PortfolioPosition.portfolio_code == portfolio_code,
            PortfolioPosition.product_code == "CASH",
        )
        .order_by(PortfolioPosition.snapshot_date.desc())
        .first()
    )
    cash = Decimal(cash_position.amount) if cash_position and cash_position.amount else Decimal("0")

    from app.models.subscription import Subscription

    confirmed_subs = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.status == "confirmed",
            Subscription.sub_type == "subscribe",
        )
        .all()
    )
    for s in confirmed_subs:
        if latest_date is None or (s.confirm_date and s.confirm_date > latest_date):
            cash += Decimal(s.amount) if s.amount else Decimal("0")

    confirmed_redeems = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.status == "confirmed",
            Subscription.sub_type == "redeem",
        )
        .all()
    )
    for s in confirmed_redeems:
        if latest_date is None or (s.confirm_date and s.confirm_date > latest_date):
            cash -= Decimal(s.amount) if s.amount else Decimal("0")

    pending_buys = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.status == "pending",
            Trade.trade_type == "buy",
        )
        .all()
    )
    for t in pending_buys:
        cash -= Decimal(t.amount) if t.amount else Decimal("0")

    confirmed_buys = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.status == "confirmed",
            Trade.trade_type == "buy",
        )
        .all()
    )
    for t in confirmed_buys:
        if latest_date is None or (t.confirm_date and t.confirm_date > latest_date):
            cash -= Decimal(t.amount) if t.amount else Decimal("0")

    confirmed_sells = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.status == "confirmed",
            Trade.trade_type == "sell",
        )
        .all()
    )
    for t in confirmed_sells:
        if latest_date is None or (t.confirm_date and t.confirm_date > latest_date):
            cash += Decimal(t.amount) if t.amount else Decimal("0")

    return cash


def _calculate_available_shares(
    db: Session, portfolio_code: str, product_code: str, market: Optional[str] = None
) -> Decimal:
    """
    基金可用份额实时计算：
    基金可用份额 = 最新快照份额
                - SUM(pending卖出份额)
                - SUM(confirmed卖出份额 WHERE 快照未生成)
    """
    latest_date = _get_latest_snapshot_date(db, portfolio_code)

    query = db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_code == portfolio_code,
        PortfolioPosition.product_code == product_code,
    )
    if market:
        query = query.filter(PortfolioPosition.market == market)
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
        if latest_date is None or (t.confirm_date and t.confirm_date > latest_date):
            shares -= Decimal(t.shares) if t.shares else Decimal("0")

    return shares


@router.get("")
def get_trades(
    portfolio_code: Optional[str] = None,
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Trade)
    if portfolio_code:
        query = query.filter(Trade.portfolio_code == portfolio_code)
    total = query.count()
    items = query.order_by(Trade.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=TradeResponse)
def create_trade(
    trade: TradeCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    # 交易日校验
    if not _is_trading_day(db, trade.trade_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "NON_TRADING_DAY", "message": "非交易日，请等待交易日再提交"},
        )

    portfolio = db.query(Portfolio).filter(Portfolio.code == trade.portfolio_code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    if portfolio.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "PORTFOLIO_NOT_ACTIVE", "message": "组合未激活"},
        )

    product = (
        db.query(Product)
        .filter(Product.code == trade.product_code, Product.market == trade.market)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if trade.trade_type == "buy":
        if trade.amount is None or trade.amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "INVALID_AMOUNT", "message": "买入金额必须大于0"},
            )
        available_cash = _calculate_available_cash(db, trade.portfolio_code)
        if Decimal(str(trade.amount)) > available_cash:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "INSUFFICIENT_CASH",
                    "message": "买入金额超过可用现金",
                },
            )
        # amount = actual_amount - fee
        actual_amount = Decimal(str(trade.actual_amount)) if trade.actual_amount else Decimal(str(trade.amount))
        fee = Decimal(str(trade.fee)) if trade.fee else Decimal("0")
        amount = actual_amount - fee
        shares = amount / Decimal(str(trade.price)) if trade.price else Decimal("0")

        new_trade = Trade(
            portfolio_code=trade.portfolio_code,
            product_code=trade.product_code,
            market=trade.market,
            platform_code=trade.platform_code,
            trade_type="buy",
            shares=shares,
            amount=amount,
            price=trade.price,
            fee=fee,
            actual_amount=actual_amount,
            trade_date=trade.trade_date,
            status="pending",
            notes=trade.notes,
        )
    elif trade.trade_type == "sell":
        if trade.shares is None or trade.shares <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "INVALID_SHARES", "message": "卖出份额必须大于0"},
            )
        available_shares = _calculate_available_shares(
            db, trade.portfolio_code, trade.product_code, trade.market
        )
        if Decimal(str(trade.shares)) > available_shares:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "INSUFFICIENT_SHARES",
                    "message": "卖出份额超过可用份额",
                },
            )
        # amount = actual_amount + fee
        actual_amount = Decimal(str(trade.actual_amount)) if trade.actual_amount else Decimal("0")
        fee = Decimal(str(trade.fee)) if trade.fee else Decimal("0")
        amount = actual_amount + fee
        shares = Decimal(str(trade.shares))

        new_trade = Trade(
            portfolio_code=trade.portfolio_code,
            product_code=trade.product_code,
            market=trade.market,
            platform_code=trade.platform_code,
            trade_type="sell",
            shares=shares,
            amount=amount,
            price=trade.price,
            fee=fee,
            actual_amount=actual_amount,
            trade_date=trade.trade_date,
            status="pending",
            notes=trade.notes,
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid trade type")

    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return new_trade


@router.get("/{id}", response_model=TradeResponse)
def get_trade(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    trade = db.query(Trade).filter(Trade.id == id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.post("/{id}/confirm")
def confirm_trade(
    id: int,
    confirm_date: Optional[date] = None,
    price: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    trade = db.query(Trade).filter(Trade.id == id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_STATUS", "message": "仅 pending 状态可确认"},
        )

    product = (
        db.query(Product)
        .filter(Product.code == trade.product_code, Product.market == trade.market)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if confirm_date is None:
        confirm_days = product.confirm_days or 0
        confirm_date = _get_next_trading_day(db, trade.trade_date, days=confirm_days)

    # 净值型产品必须获取净值进行计算
    # 判断是否为净值型产品（场外基金）
    is_nav_product = product.product_type in ["OEF", "LOF"] and trade.market == "CN_OTC"
    
    if is_nav_product:
        # 净值型产品：获取T日净值（QDII会抛出异常如果净值不存在）
        nav_price = _get_nav_for_trade_confirmation(
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
        
        # 如果前端传入了价格，使用传入的价格；否则使用系统获取的净值
        final_price = Decimal(str(price)) if price is not None else nav_price
        
        # 重新计算交易数据
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
    trade.confirm_date = confirm_date
    db.commit()
    db.refresh(trade)
    resp = TradeResponse.from_orm(trade)
    return {
        "message": "Trade confirmed successfully",
        "id": resp.id,
        "portfolio_code": resp.portfolio_code,
        "trade_type": resp.trade_type,
        "status": resp.status,
        "confirm_date": resp.confirm_date,
        "trade": resp,
    }


@router.post("/{id}/cancel")
def cancel_trade(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    trade = db.query(Trade).filter(Trade.id == id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_STATUS", "message": "仅 pending 状态可取消"},
        )

    # 仅场外 pending 可取消（场内当天确认，一般不允许取消）
    # 但规则说"仅场外 pending 可取消"，这里校验 market
    if trade.market == "CN_EXCHANGE":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "CANNOT_CANCEL_EXCHANGE", "message": "场内交易不可取消"},
        )

    trade.status = "cancelled"
    db.commit()
    return {"message": "Trade cancelled successfully"}


@router.put("/{id}", response_model=TradeResponse)
def update_trade(
    id: int,
    trade: TradeUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    db_trade = db.query(Trade).filter(Trade.id == id).first()
    if not db_trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    if db_trade.status == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "CANNOT_MODIFY_CONFIRMED",
                "message": "已确认的交易不可直接修改，请先取消确认后再修改"
            }
        )

    for field, value in trade.dict(exclude_unset=True).items():
        setattr(db_trade, field, value)

    db.commit()
    db.refresh(db_trade)
    return db_trade


@router.delete("/{id}")
def delete_trade(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    trade = db.query(Trade).filter(Trade.id == id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    if trade.status == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "CANNOT_DELETE_CONFIRMED",
                "message": "已确认的交易不可直接删除，请先取消确认后再删除"
            }
        )

    db.delete(trade)
    db.commit()
    return {"message": "Trade deleted successfully"}
