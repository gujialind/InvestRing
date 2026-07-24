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


@app.command("delete-bulk")
def delete_snapshots_bulk(
    portfolio_code: str = typer.Argument(...),
    from_date: str = typer.Argument(..., help="YYYY-MM-DD，含当日"),
    yes: bool = typer.Option(False, "--yes", help="跳过确认，未提供则拒绝执行"),
):
    """批量删除从 from_date 起（含当日）的所有快照，从最新日倒序级联回退"""
    if not yes:
        error("CONFIRM_REQUIRED", "批量删除快照不可逆，请追加 --yes 确认")
    with cli_context() as db:
        from app.services.snapshot_service import _delete_existing_snapshots
        from app.models.portfolio_value_snapshot import PortfolioValueSnapshot

        fd = parse_date(from_date)
        snapshot_dates = [
            row[0] for row in db.query(PortfolioValueSnapshot.snapshot_date)
            .filter(
                PortfolioValueSnapshot.portfolio_code == portfolio_code,
                PortfolioValueSnapshot.snapshot_date >= fd,
            )
            .order_by(PortfolioValueSnapshot.snapshot_date.desc())
            .all()
        ]

        if not snapshot_dates:
            success(data={
                "message": f"组合 {portfolio_code} 在 {fd} 之后无快照可删除",
                "deleted_count": 0,
            })

        total_subs = 0
        total_events = 0
        details = []
        for sd in snapshot_dates:
            result = _delete_existing_snapshots(db, portfolio_code, sd)
            subs = result.get("cascaded_subscriptions", [])
            events = result.get("cascaded_events", [])
            total_subs += len(subs)
            total_events += len(events)
            details.append({
                "snapshot_date": sd.isoformat(),
                "deleted": result["deleted"],
                "cascaded_subs": len(subs),
                "cascaded_events": len(events),
            })
            db.flush()

        success(data={
            "message": f"已删除组合 {portfolio_code} 从 {fd} 起的 {len(snapshot_dates)} 个快照"
                       f"（级联回退 {total_subs} 笔申购/赎回，{total_events} 笔事件）",
            "deleted_count": len(snapshot_dates),
            "details": details,
        })
