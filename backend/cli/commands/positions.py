"""
ir position - 持仓管理命令组
"""
import sys
import typer
from typing import Optional
from decimal import Decimal
from sqlalchemy import func

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta, parse_date

app = typer.Typer(no_args_is_help=True)


def _resolve_required(option_value: Optional[str], arg_value: Optional[str], flag: str) -> str:
    """option 优先；位置参数已弃用（issue #81），仅向 stderr 告警避免污染 stdout JSON"""
    if option_value is not None:
        return option_value
    if arg_value is not None:
        print(f"[warning] 位置参数已弃用，请改用 {flag} 选项", file=sys.stderr)
        return arg_value
    error("VALIDATION_ERROR", f"缺少 {flag}")


@app.command("list")
def list_positions(
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
    snapshot_date: str = typer.Option(None, "--snapshot-date", help="YYYY-MM-DD"),
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
):
    """查看持仓（默认最新快照）"""
    with cli_context() as db:
        from app.models.portfolio_position import PortfolioPosition

        sd = parse_date(snapshot_date) if snapshot_date else None
        query = db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == portfolio_code
        )
        if sd:
            query = query.filter(PortfolioPosition.snapshot_date == sd)
        else:
            subq = (
                db.query(
                    PortfolioPosition.portfolio_code,
                    PortfolioPosition.product_code,
                    func.max(PortfolioPosition.snapshot_date).label("max_date"),
                )
                .group_by(PortfolioPosition.portfolio_code, PortfolioPosition.product_code)
                .subquery()
            )
            query = query.join(
                subq,
                (PortfolioPosition.portfolio_code == subq.c.portfolio_code)
                & (PortfolioPosition.product_code == subq.c.product_code)
                & (PortfolioPosition.snapshot_date == subq.c.max_date),
            )
        items, total, page, page_size = paginate(query, page, page_size, False)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("get")
def get_position(
    id: int = typer.Argument(...),
):
    """查看单条持仓详情"""
    with cli_context() as db:
        from app.models.portfolio_position import PortfolioPosition

        pos = db.query(PortfolioPosition).filter(PortfolioPosition.id == id).first()
        if not pos:
            error("NOT_FOUND", f"持仓记录 {id} 不存在")
        success(data=serialize_model(pos))


@app.command("available-cash")
def available_cash(
    portfolio_code_arg: Optional[str] = typer.Argument(None, metavar="[PORTFOLIO_CODE]", help="[deprecated] 请改用 --portfolio-code"),
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="组合代码"),
):
    """查看组合可用现金（实时计算）"""
    code = _resolve_required(portfolio_code, portfolio_code_arg, "--portfolio-code")
    with cli_context() as db:
        from app.services.position_service import calculate_available_cash

        cash = calculate_available_cash(db, code)
        success(data={"portfolio_code": code, "available_cash": float(cash)})


@app.command("available-shares")
def available_shares(
    portfolio_code_arg: Optional[str] = typer.Argument(None, metavar="[PORTFOLIO_CODE]", help="[deprecated] 请改用 --portfolio-code"),
    product_code_arg: Optional[str] = typer.Argument(None, metavar="[PRODUCT_CODE]", help="[deprecated] 请改用 --product-code"),
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="组合代码"),
    product_code: Optional[str] = typer.Option(None, "--product-code", help="产品代码"),
    market: Optional[str] = typer.Option(None, "--market"),
):
    """查看产品可用份额（实时计算）"""
    pf_code = _resolve_required(portfolio_code, portfolio_code_arg, "--portfolio-code")
    prod_code = _resolve_required(product_code, product_code_arg, "--product-code")
    with cli_context() as db:
        from app.services.position_service import calculate_available_shares

        shares = calculate_available_shares(db, pf_code, prod_code, market)
        success(data={
            "portfolio_code": pf_code,
            "product_code": prod_code,
            "market": market,
            "available_shares": float(shares),
        })


@app.command("update-cash")
def update_cash_position(
    portfolio_code: str = typer.Argument(...),
    platform_code: str = typer.Option(..., "--platform-code"),
    cash_amount: float = typer.Option(..., "--cash-amount"),
    update_date: str = typer.Option(None, "--update-date", help="YYYY-MM-DD"),
):
    """更新现金市值（写入 manual_market_value，绝对替换，不直接写快照表）"""
    with cli_context() as db:
        from app.services.position_service import update_cash_position as update_cash_service

        result = update_cash_service(
            db,
            portfolio_code=portfolio_code,
            platform_code=platform_code,
            amount=Decimal(str(cash_amount)),
            update_date=parse_date(update_date) if update_date else None,
        )
        success(data={
            "message": "现金市值覆盖已写入 manual_market_value，建议重新生成快照以更新持仓",
            "portfolio_code": result["portfolio_code"],
            "platform_code": result["platform_code"],
            "cash_amount": result["cash_amount"],
            "computed_value": result["computed_value"],
            "update_date": result["update_date"].isoformat(),
            "requires_snapshot_regen": True,
            "warnings": result["warnings"],
        })


@app.command("list-cash-overrides")
def list_cash_overrides(
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
    platform_code: Optional[str] = typer.Option(None, "--platform-code", help="平台代码"),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="YYYY-MM-DD"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="YYYY-MM-DD"),
):
    """查询现金手动覆盖记录（manual_market_value，issue #88）"""
    with cli_context() as db:
        from app.services.position_service import list_manual_cash_overrides

        items = list_manual_cash_overrides(
            db,
            portfolio_code,
            platform_code=platform_code,
            start_date=parse_date(start_date) if start_date else None,
            end_date=parse_date(end_date) if end_date else None,
        )
        for item in items:
            item["value_date"] = item["value_date"].isoformat()
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
        success(data=items, meta={"total": len(items)})


@app.command("delete-cash")
def delete_cash_override(
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
    platform_code: str = typer.Option(..., "--platform-code", help="平台代码"),
    update_date: str = typer.Option(..., "--update-date", help="YYYY-MM-DD，覆盖记录日期"),
):
    """删除现金手动覆盖记录（issue #88），删除后该日回退自然计算值（需重算快照生效）"""
    with cli_context() as db:
        from app.services.position_service import delete_manual_cash_override

        result = delete_manual_cash_override(
            db,
            portfolio_code=portfolio_code,
            platform_code=platform_code,
            value_date=parse_date(update_date),
        )
        success(data={
            "message": f"已删除 {portfolio_code}/{platform_code} 在 {update_date} 的现金覆盖记录",
            "portfolio_code": result["portfolio_code"],
            "platform_code": result["platform_code"],
            "update_date": result["value_date"].isoformat(),
            "deleted_value": result["deleted_value"],
            "requires_snapshot_regen": result["requires_snapshot_regen"],
        })
