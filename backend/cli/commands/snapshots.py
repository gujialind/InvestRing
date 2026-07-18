"""
ir snapshot - 快照管理命令组
"""
import typer
from typing import Optional
from sqlalchemy import func

from cli.context import cli_context
from cli.output import success, error
from cli.utils import parse_date

app = typer.Typer(no_args_is_help=True)


@app.command("generate")
def generate_snapshot(
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
    target_date: str = typer.Option(..., "--target-date", help="YYYY-MM-DD"),
):
    """生成单日快照"""
    with cli_context() as db:
        from app.services.snapshot_service import generate_daily_snapshots

        result = generate_daily_snapshots(db, portfolio_code, parse_date(target_date))
        success(data=result)


@app.command("recalculate")
def recalculate_snapshots(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="为空则重算所有活跃组合"),
    start_date: str = typer.Option(..., "--start-date", help="YYYY-MM-DD"),
    end_date: str = typer.Option(..., "--end-date", help="YYYY-MM-DD"),
):
    """区间重算快照"""
    with cli_context() as db:
        from app.services.snapshot_service import recalculate_snapshots as recalc

        result = recalc(db, portfolio_code, parse_date(start_date), parse_date(end_date))
        success(data=result)


@app.command("validate")
def validate_dependencies(
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
    target_date: str = typer.Option(..., "--target-date", help="YYYY-MM-DD"),
):
    """校验指定日期的快照依赖数据"""
    with cli_context() as db:
        from app.services.snapshot_service import validate_snapshot_dependencies

        td = parse_date(target_date)
        checks = validate_snapshot_dependencies(db, portfolio_code, td)
        is_valid = all(c.get("is_valid", False) for c in checks) if checks else False
        success(data={"portfolio_code": portfolio_code, "target_date": td.isoformat(),
                       "is_valid": is_valid, "checks": checks})


@app.command("status")
def snapshot_status(
    portfolio_code: str = typer.Argument(...),
):
    """查看快照状态"""
    with cli_context() as db:
        from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
        from app.models.portfolio_position import PortfolioPosition
        from app.models.investor_holding import InvestorHolding

        nav_count = db.query(PortfolioValueSnapshot).filter(
            PortfolioValueSnapshot.portfolio_code == portfolio_code
        ).count()

        latest_date = db.query(func.max(PortfolioValueSnapshot.snapshot_date)).filter(
            PortfolioValueSnapshot.portfolio_code == portfolio_code
        ).scalar()

        earliest_date = db.query(func.min(PortfolioValueSnapshot.snapshot_date)).filter(
            PortfolioValueSnapshot.portfolio_code == portfolio_code
        ).scalar()

        success(data={
            "portfolio_code": portfolio_code,
            "nav_snapshot_count": nav_count,
            "latest_date": latest_date.isoformat() if latest_date else None,
            "earliest_date": earliest_date.isoformat() if earliest_date else None,
        })


@app.command("delete")
def delete_snapshot(
    portfolio_code: str = typer.Argument(...),
    snapshot_date: str = typer.Argument(..., help="YYYY-MM-DD"),
    yes: bool = typer.Option(False, "--yes"),
):
    """删除指定日期的快照（自动级联回退依赖该快照的申购/赎回）"""
    with cli_context() as db:
        from app.services.snapshot_service import _delete_existing_snapshots

        sd = parse_date(snapshot_date)
        result = _delete_existing_snapshots(db, portfolio_code, sd)
        db.flush()

        output = {
            "message": f"快照 {sd} 已删除",
            "deleted": result["deleted"],
        }
        cascaded = result.get("cascaded_subscriptions", [])
        if cascaded:
            output["cascaded_subscriptions"] = cascaded
            output["message"] += f"（级联回退了 {len(cascaded)} 笔申购/赎回）"

        success(data=output)
