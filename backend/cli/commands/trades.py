"""
ir trade - 调仓交易命令组
"""
import typer
from typing import Optional
from decimal import Decimal

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta, parse_date

app = typer.Typer(no_args_is_help=True)


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
    allow_duplicate: bool = typer.Option(
        False, "--allow-duplicate", help="强制创建与既有 pending/confirmed 交易同参数的重复交易"
    ),
):
    """创建买入/卖出交易（校验/配对 CASH 腿由服务层统一处理）"""
    with cli_context() as db:
        from app.services.trade_service import create_trade as create_trade_service

        new_trade = create_trade_service(
            db,
            portfolio_code=portfolio_code,
            product_code=product_code,
            market=market,
            trade_type=trade_type,
            trade_date=parse_date(trade_date),
            actual_amount=Decimal(str(actual_amount)) if actual_amount is not None else None,
            fee=Decimal(str(fee)),
            price=Decimal(str(price)) if price is not None else None,
            shares=Decimal(str(shares)) if shares is not None else None,
            platform_code=platform_code,
            notes=notes,
            allow_duplicate=allow_duplicate,
        )
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


@app.command("preview")
def preview_trade(
    id: int = typer.Argument(...),
    confirm_date: str = typer.Option(None, "--confirm-date", help="YYYY-MM-DD"),
    price: Optional[float] = typer.Option(None, "--price"),
):
    """确认前预览：返回真实确认将写入的净值/份额/金额，不落库（与 confirm 共用计算实现）"""
    with cli_context() as db:
        from app.models.trade import Trade
        from app.models.product import Product
        from app.services.trade_service import calculate_confirm_preview

        trade = db.query(Trade).filter(Trade.id == id).first()
        if not trade:
            error("NOT_FOUND", f"交易记录 {id} 不存在")
        if trade.status != "pending":
            error("INVALID_STATUS", "仅 pending 状态可预览确认结果")

        product = db.query(Product).filter(
            Product.code == trade.product_code, Product.market == trade.market
        ).first()
        if not product:
            error("NOT_FOUND", f"产品 {trade.product_code} 不存在")

        cd = parse_date(confirm_date) if confirm_date else None
        price_d = Decimal(str(price)) if price is not None else None
        preview = calculate_confirm_preview(db, trade, product, confirm_date=cd, price=price_d)
        # 结构对齐 REST GET /api/trades/{id}/preview：trade + preview + paired_cash_amount
        success(data={
            "trade": serialize_model(trade),
            "preview": {k: v for k, v in preview.items() if k != "paired_cash_amount"},
            "paired_cash_amount": preview["paired_cash_amount"],
        })


@app.command("confirm")
def confirm_trade(
    id: int = typer.Argument(...),
    confirm_date: str = typer.Option(None, "--confirm-date", help="YYYY-MM-DD"),
    price: Optional[float] = typer.Option(None, "--price"),
):
    """确认交易（委托服务层：T 日净值、配对 CASH 腿原子同步）"""
    with cli_context() as db:
        from app.models.trade import Trade
        from app.models.product import Product
        from app.services.trade_service import confirm_single_trade

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
        price_d = Decimal(str(price)) if price is not None else None
        confirm_single_trade(db, trade, product, confirm_date=cd, price=price_d)
        db.flush()
        db.refresh(trade)
        success(data={"message": "交易确认成功", "trade": serialize_model(trade)})


@app.command("cancel")
def cancel_trade(
    id: int = typer.Argument(...),
):
    """取消交易（仅 pending + 非场内，配对 CASH 腿自动同步）"""
    with cli_context() as db:
        from app.models.trade import Trade
        from app.services.trade_service import cancel_trade as cancel_trade_service

        trade = db.query(Trade).filter(Trade.id == id).first()
        if not trade:
            error("NOT_FOUND", f"交易记录 {id} 不存在")
        cancel_trade_service(db, trade)
        db.flush()
        success(data={"message": "交易已取消", "id": id})


@app.command("unconfirm")
def unconfirm_trade(
    id: int = typer.Argument(...),
):
    """取消确认（confirmed -> pending，快照保护 + 配对腿同步）"""
    with cli_context() as db:
        from app.models.trade import Trade
        from app.services.trade_service import unconfirm_trade as unconfirm_trade_service

        trade = db.query(Trade).filter(Trade.id == id).first()
        if not trade:
            error("NOT_FOUND", f"交易记录 {id} 不存在")
        unconfirm_trade_service(db, trade)
        db.flush()
        success(data={"message": "交易已取消确认", "id": id})
