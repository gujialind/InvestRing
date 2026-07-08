"""
ir cash-transfer - 平台间现金转移命令组
"""
import uuid
import typer
from typing import Optional
from decimal import Decimal

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, parse_date


app = typer.Typer(no_args_is_help=True)


@app.command("create")
def create_cash_transfer(
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
    from_platform: str = typer.Option(..., "--from", help="转出平台代码"),
    to_platform: str = typer.Option(..., "--to", help="转入平台代码"),
    amount: float = typer.Option(..., "--amount", help="转移金额"),
    transfer_date: str = typer.Option(..., "--date", help="转出日期 YYYY-MM-DD"),
    cross_day: bool = typer.Option(False, "--cross-day", help="跨天到账（T+1确认）"),
    notes: Optional[str] = typer.Option(None, "--notes"),
):
    """创建平台间现金转移"""
    with cli_context() as db:
        from app.models.portfolio import Portfolio
        from app.models.platform import Platform
        from app.models.trade import Trade
        from app.services.trading_utils import is_trading_day
        from app.services.position_service import calculate_available_cash

        td = parse_date(transfer_date)

        # 校验交易日
        if not is_trading_day(db, td):
            error("NON_TRADING_DAY", "非交易日，请等待交易日再提交")

        # 校验组合
        portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
        if not portfolio:
            error("NOT_FOUND", f"组合 {portfolio_code} 不存在")
        if portfolio.status != "active":
            error("PORTFOLIO_NOT_ACTIVE", "组合未激活")

        # 校验平台
        if from_platform == to_platform:
            error("SAME_PLATFORM", "转出平台和转入平台不能相同")
        fp = db.query(Platform).filter(Platform.code == from_platform).first()
        if not fp:
            error("PLATFORM_NOT_FOUND", f"转出平台 {from_platform} 不存在")
        tp = db.query(Platform).filter(Platform.code == to_platform).first()
        if not tp:
            error("PLATFORM_NOT_FOUND", f"转入平台 {to_platform} 不存在")

        # 校验金额
        if amount <= 0:
            error("INVALID_AMOUNT", "转移金额必须大于0")

        # 校验转出平台可用现金
        available = calculate_available_cash(db, portfolio_code, from_platform)
        if Decimal(str(amount)) > available:
            error("INSUFFICIENT_CASH", f"平台 {from_platform} 可用现金不足（当前: {float(available)}）")

        transfer_group = uuid.uuid4().hex[:12]
        amt = Decimal(str(amount))

        # 卖出 CASH（转出）
        sell_trade = Trade(
            portfolio_code=portfolio_code, platform_code=from_platform,
            product_code="CASH", market="", trade_type="sell",
            transfer_group=transfer_group, amount=amt, price=Decimal("1"),
            fee=Decimal("0"), actual_amount=amt, trade_date=td,
            status="pending", notes=notes or f"现金转移至 {to_platform}",
        )
        db.add(sell_trade)
        db.flush()

        # 买入 CASH（转入）
        buy_trade = Trade(
            portfolio_code=portfolio_code, platform_code=to_platform,
            product_code="CASH", market="", trade_type="buy",
            transfer_group=transfer_group, amount=amt, price=Decimal("1"),
            fee=Decimal("0"), actual_amount=amt, trade_date=td,
            status="pending", notes=notes or f"现金从 {from_platform} 转入",
        )
        db.add(buy_trade)
        db.flush()

        # 确认策略
        if not cross_day:
            sell_trade.status = "confirmed"
            sell_trade.confirm_date = td
            buy_trade.status = "confirmed"
            buy_trade.confirm_date = td
        else:
            sell_trade.status = "confirmed"
            sell_trade.confirm_date = td
            buy_trade.status = "pending"

        db.flush()
        db.refresh(sell_trade)
        db.refresh(buy_trade)

        success(data={
            "transfer_group": transfer_group,
            "from_platform": from_platform,
            "to_platform": to_platform,
            "amount": float(amt),
            "cross_day": cross_day,
            "sell_trade_id": sell_trade.id,
            "sell_status": sell_trade.status,
            "buy_trade_id": buy_trade.id,
            "buy_status": buy_trade.status,
        })


@app.command("list")
def list_cash_transfers(
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
):
    """查询现金转移记录"""
    with cli_context() as db:
        from app.models.trade import Trade

        trades = (
            db.query(Trade)
            .filter(
                Trade.portfolio_code == portfolio_code,
                Trade.transfer_group.isnot(None),
                Trade.product_code == "CASH",
            )
            .order_by(Trade.created_at.desc())
            .all()
        )

        groups = {}
        for t in trades:
            if t.transfer_group not in groups:
                groups[t.transfer_group] = {"sell": None, "buy": None}
            if t.trade_type == "sell":
                groups[t.transfer_group]["sell"] = t
            elif t.trade_type == "buy":
                groups[t.transfer_group]["buy"] = t

        items = []
        for tg, pair in groups.items():
            sell = pair.get("sell")
            buy = pair.get("buy")
            if not sell or not buy:
                continue
            items.append({
                "transfer_group": tg,
                "from_platform": sell.platform_code,
                "to_platform": buy.platform_code,
                "amount": float(sell.amount or 0),
                "sell_status": sell.status,
                "buy_status": buy.status,
                "transfer_date": sell.trade_date.isoformat() if sell.trade_date else None,
                "sell_confirm_date": sell.confirm_date.isoformat() if sell.confirm_date else None,
                "buy_confirm_date": buy.confirm_date.isoformat() if buy.confirm_date else None,
            })
        success(data=items, meta={"total": len(items)})


@app.command("confirm")
def confirm_cash_transfer(
    transfer_group: str = typer.Argument(..., help="转移组标识"),
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
):
    """确认跨天转移的买入交易"""
    with cli_context() as db:
        from app.models.trade import Trade
        from datetime import date
        from sqlalchemy import func
        from app.models.trading_calendar import TradingCalendar

        buy_trade = (
            db.query(Trade)
            .filter(
                Trade.portfolio_code == portfolio_code,
                Trade.transfer_group == transfer_group,
                Trade.product_code == "CASH",
                Trade.trade_type == "buy",
            )
            .first()
        )
        if not buy_trade:
            error("TRANSFER_NOT_FOUND", f"未找到转移记录 {transfer_group}")
        if buy_trade.status != "pending":
            error("INVALID_STATUS", "该买入交易已确认或已取消")

        # 计算下一个交易日
        confirm_date = (
            db.query(func.min(TradingCalendar.date))
            .filter(
                TradingCalendar.date > buy_trade.trade_date,
                TradingCalendar.is_open == True,
            )
            .scalar()
        )
        if not confirm_date:
            confirm_date = buy_trade.trade_date
        if confirm_date > date.today():
            error("TRANSFER_NOT_READY", f"跨天转移尚未到确认日期（预计: {confirm_date}）")

        buy_trade.status = "confirmed"
        buy_trade.confirm_date = confirm_date
        db.flush()
        db.refresh(buy_trade)
        success(data={
            "message": "跨天转移确认成功",
            "transfer_group": transfer_group,
            "buy_trade_id": buy_trade.id,
            "status": buy_trade.status,
            "confirm_date": buy_trade.confirm_date.isoformat() if buy_trade.confirm_date else None,
        })
