"""
ir trade - 调仓交易命令组
"""
import typer
from typing import Optional
from datetime import date
from decimal import Decimal

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta, parse_date

app = typer.Typer(no_args_is_help=True)


def _get_nav_for_confirmation(db, product_code: str, market: str, trade_date: date, is_qdii: bool):
    """获取调仓交易确认时的净值"""
    from app.models.price_record import PriceRecord

    if is_qdii:
        pr = db.query(PriceRecord).filter(
            PriceRecord.product_code == product_code,
            PriceRecord.market == market,
            PriceRecord.date == trade_date,
        ).first()
        if not pr or not pr.unit_price:
            raise ValueError(
                f"QDII产品{product_code}在T={trade_date}的净值尚未同步，"
                f"请等待T+2日后重试或手动指定价格"
            )
        return Decimal(str(pr.unit_price))
    else:
        pr = db.query(PriceRecord).filter(
            PriceRecord.product_code == product_code,
            PriceRecord.market == market,
            PriceRecord.date <= trade_date,
        ).order_by(PriceRecord.date.desc()).first()
        if pr and pr.unit_price:
            return Decimal(str(pr.unit_price))
        return None


@app.command("list")
def list_trades(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code"),
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
    all: bool = typer.Option(False, "--all"),
):
    """获取调仓交易列表"""
    with cli_context() as db:
        from app.models.trade import Trade

        query = db.query(Trade).order_by(Trade.created_at.desc())
        if portfolio_code:
            query = query.filter(Trade.portfolio_code == portfolio_code)
        items, total, page, page_size = paginate(query, page, page_size, all)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("create")
def create_trade(
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
    product_code: str = typer.Option(..., "--product-code"),
    market: str = typer.Option(..., "--market"),
    trade_type: str = typer.Option(..., "--type", help="buy/sell"),
    actual_amount: Optional[float] = typer.Option(None, "--actual-amount"),
    fee: float = typer.Option(0.0, "--fee"),
    price: Optional[float] = typer.Option(None, "--price"),
    shares: Optional[float] = typer.Option(None, "--shares"),
    platform_code: Optional[str] = typer.Option(None, "--platform-code"),
    trade_date: str = typer.Option(..., "--trade-date", help="YYYY-MM-DD"),
    notes: Optional[str] = typer.Option(None, "--notes"),
):
    """创建买入/卖出交易"""
    with cli_context() as db:
        from app.models.trade import Trade
        from app.models.portfolio import Portfolio
        from app.models.product import Product
        from app.services.trading_utils import is_trading_day
        from app.services.position_service import calculate_available_cash, calculate_available_shares

        td = parse_date(trade_date)
        if not is_trading_day(db, td):
            error("NON_TRADING_DAY", "非交易日，请等待交易日再提交")

        portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
        if not portfolio:
            error("NOT_FOUND", "组合不存在")
        if portfolio.status != "active":
            error("PORTFOLIO_NOT_ACTIVE", "组合未激活")

        product = db.query(Product).filter(
            Product.code == product_code, Product.market == market
        ).first()
        if not product:
            error("NOT_FOUND", f"产品 {product_code}({market}) 不存在")

        fee_d = Decimal(str(fee))

        if trade_type == "buy":
            if not actual_amount or actual_amount <= 0:
                error("INVALID_AMOUNT", "买入实际金额必须大于0")
            available_cash = calculate_available_cash(db, portfolio_code)
            if Decimal(str(actual_amount)) > available_cash:
                error("INSUFFICIENT_CASH", f"买入金额超过可用现金({float(available_cash)})")
            actual_amount_d = Decimal(str(actual_amount))
            amount = actual_amount_d - fee_d
            price_d = Decimal(str(price)) if price else Decimal("0")
            shares_d = amount / price_d if price_d else Decimal("0")
            new_trade = Trade(
                portfolio_code=portfolio_code, product_code=product_code, market=market,
                platform_code=platform_code, trade_type="buy",
                shares=shares_d, amount=amount, price=price_d, fee=fee_d,
                actual_amount=actual_amount_d, trade_date=td,
                status="pending", notes=notes,
            )
        elif trade_type == "sell":
            if not shares or shares <= 0:
                error("INVALID_SHARES", "卖出份额必须大于0")
            available_shares = calculate_available_shares(db, portfolio_code, product_code, market)
            if Decimal(str(shares)) > available_shares:
                error("INSUFFICIENT_SHARES", f"卖出份额超过可用份额({float(available_shares)})")
            shares_d = Decimal(str(shares))
            actual_amount_d = Decimal(str(actual_amount)) if actual_amount else Decimal("0")
            amount = actual_amount_d + fee_d
            new_trade = Trade(
                portfolio_code=portfolio_code, product_code=product_code, market=market,
                platform_code=platform_code, trade_type="sell",
                shares=shares_d, amount=amount, price=price, fee=fee_d,
                actual_amount=actual_amount_d, trade_date=td,
                status="pending", notes=notes,
            )
        else:
            error("INVALID_TYPE", "类型必须为 buy 或 sell")

        db.add(new_trade)
        db.flush()
        db.refresh(new_trade)
        success(data=serialize_model(new_trade))


@app.command("get")
def get_trade(
    id: int = typer.Argument(...),
):
    """查看交易详情"""
    with cli_context() as db:
        from app.models.trade import Trade

        trade = db.query(Trade).filter(Trade.id == id).first()
        if not trade:
            error("NOT_FOUND", f"交易记录 {id} 不存在")
        success(data=serialize_model(trade))


@app.command("confirm")
def confirm_trade(
    id: int = typer.Argument(...),
    confirm_date: str = typer.Option(None, "--confirm-date", help="YYYY-MM-DD"),
    price: Optional[float] = typer.Option(None, "--price"),
):
    """确认交易（自动获取净值，QDII 特殊处理）"""
    with cli_context() as db:
        from app.models.trade import Trade
        from app.models.product import Product
        from app.services.trading_utils import get_next_trading_day

        trade = db.query(Trade).filter(Trade.id == id).first()
        if not trade:
            error("NOT_FOUND", f"交易记录 {id} 不存在")
        if trade.status != "pending":
            error("INVALID_STATUS", "仅 pending 状态可确认")

        product = db.query(Product).filter(
            Product.code == trade.product_code, Product.market == trade.market
        ).first()
        if not product:
            error("NOT_FOUND", f"产品 {trade.product_code} 不存在")

        cd = parse_date(confirm_date) if confirm_date else None
        if cd is None:
            confirm_days = product.confirm_days or 0
            confirm_date = get_next_trading_day(db, trade.trade_date, days=confirm_days)
        else:
            confirm_date = cd

        is_nav_product = product.product_type in ["OEF", "LOF"] and trade.market == "CN_OTC"

        if is_nav_product:
            nav_price = _get_nav_for_confirmation(
                db, trade.product_code, trade.market, trade.trade_date, product.is_qdii
            )
            if nav_price is None and price is None:
                error("MISSING_NAV", f"产品{trade.product_code}在T={trade.trade_date}的净值尚未同步，请手动指定 --price")
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
        db.flush()
        db.refresh(trade)
        success(data={"message": "交易确认成功", "trade": serialize_model(trade)})


@app.command("cancel")
def cancel_trade(
    id: int = typer.Argument(...),
):
    """取消交易（仅 pending + 非场内）"""
    with cli_context() as db:
        from app.models.trade import Trade

        trade = db.query(Trade).filter(Trade.id == id).first()
        if not trade:
            error("NOT_FOUND", f"交易记录 {id} 不存在")
        if trade.status != "pending":
            error("INVALID_STATUS", "仅 pending 状态可取消")
        if trade.market == "CN_EXCHANGE":
            error("CANNOT_CANCEL_EXCHANGE", "场内交易不可取消")
        trade.status = "cancelled"
        db.flush()
        success(data={"message": "交易已取消", "id": id})


@app.command("unconfirm")
def unconfirm_trade(
    id: int = typer.Argument(...),
):
    """取消确认（confirmed -> pending）"""
    with cli_context() as db:
        from app.models.trade import Trade

        trade = db.query(Trade).filter(Trade.id == id).first()
        if not trade:
            error("NOT_FOUND", f"交易记录 {id} 不存在")
        if trade.status != "confirmed":
            error("INVALID_STATUS", "仅 confirmed 状态可取消确认")
        trade.status = "pending"
        trade.confirm_date = None
        db.flush()
        success(data={"message": "交易已取消确认", "id": id})
