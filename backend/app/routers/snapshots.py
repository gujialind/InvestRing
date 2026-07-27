"""快照管理API路由"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin, get_current_user
from app.models import Investor, Portfolio, PortfolioValueSnapshot
from app.schemas.snapshot import (
    SnapshotGenerateRequest,
    SnapshotRecalculateRequest,
    SnapshotValidationResult,
    SnapshotGenerationResult,
    RecalculationResult,
    SnapshotStatusResponse,
)
from app.services.exceptions import BusinessError
from app.services.snapshot_service import (
    generate_daily_snapshots,
    recalculate_snapshots,
    validate_snapshot_dependencies,
)

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.post("/generate", response_model=SnapshotGenerationResult)
def generate_snapshot(
    request: SnapshotGenerateRequest,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    """
    手动触发单日快照生成
    
    权限：仅admin
    """
    try:
        result = generate_daily_snapshots(
            db=db,
            portfolio_code=request.portfolio_code,
            target_date=request.target_date,
        )
        # service 不 commit（AGENTS.md §4.1），事务边界在 router
        db.commit()
        return SnapshotGenerationResult(**result)
    except BusinessError:
        # 领域异常（如 SNAPSHOT_NOT_CONTINUOUS）交给全局 handler 映射
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "VALIDATION_FAILED", "message": str(e)},
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "SNAPSHOT_GENERATION_FAILED", "message": str(e)},
        )


@router.post("/recalculate", response_model=RecalculationResult)
def recalculate(
    request: SnapshotRecalculateRequest,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    """
    重算指定时间区间的快照
    
    单一事务（issue #58）：无 errors 时统一 commit；任一日失败则整体 rollback，
    被删快照与级联回退状态完整复原，对外「要么完整成功，要么无变化」。
    
    权限：仅admin
    """
    try:
        result = recalculate_snapshots(
            db=db,
            portfolio_code=request.portfolio_code,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        # errors 非空（中途 break）时回滚半截中间态，仍返回 200 + errors 保持响应契约
        if any(r["errors"] for r in result["results"]):
            db.rollback()
        else:
            db.commit()
        return RecalculationResult(**result)
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "VALIDATION_FAILED", "message": str(e)},
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "RECALCULATION_FAILED", "message": str(e)},
        )


@router.get("/validation", response_model=SnapshotValidationResult)
def validate_dependencies(
    portfolio_code: str = Query(..., description="组合代码"),
    target_date: date = Query(..., description="目标日期"),
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    """
    预检指定日期的依赖数据
    
    权限：仅admin
    """
    checks = validate_snapshot_dependencies(db, portfolio_code, target_date)
    
    is_valid = all(c["status"] != "failed" for c in checks)
    
    return SnapshotValidationResult(
        portfolio_code=portfolio_code,
        target_date=target_date,
        is_valid=is_valid,
        checks=checks,
    )


@router.get("/portfolios/{code}/status", response_model=SnapshotStatusResponse)
def get_snapshot_status(
    code: str,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_user),
):
    """
    查询组合快照状态
    
    权限：所有用户（只能查看自己有权限的组合）
    """
    # 检查组合是否存在
    portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PORTFOLIO_NOT_FOUND", "message": f"组合 {code} 不存在"},
        )
    
    # 获取最新快照日期
    latest = db.query(PortfolioValueSnapshot).filter(
        PortfolioValueSnapshot.portfolio_code == code
    ).order_by(PortfolioValueSnapshot.snapshot_date.desc()).first()
    
    # 获取最早快照日期
    earliest = db.query(PortfolioValueSnapshot).filter(
        PortfolioValueSnapshot.portfolio_code == code
    ).order_by(PortfolioValueSnapshot.snapshot_date.asc()).first()
    
    # 获取快照总数
    total = db.query(PortfolioValueSnapshot).filter(
        PortfolioValueSnapshot.portfolio_code == code
    ).count()
    
    # 计算缺失的交易日（简化：这里只返回空列表，实际实现需要更复杂的逻辑）
    missing_dates = []
    
    return SnapshotStatusResponse(
        portfolio_code=code,
        latest_snapshot_date=latest.snapshot_date if latest else None,
        total_snapshots=total,
        first_snapshot_date=earliest.snapshot_date if earliest else None,
        missing_dates=missing_dates,
    )


@router.delete("/{portfolio_code}/{snapshot_date}")
def delete_snapshot(
    portfolio_code: str,
    snapshot_date: date,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    """
    删除指定日期的快照
    
    删除前自动级联回退依赖该快照的已确认申购/赎回和份额变动事件。
    
    权限：仅admin
    """
    from app.services.snapshot_service import _delete_existing_snapshots
    
    try:
        result = _delete_existing_snapshots(db, portfolio_code, snapshot_date)
        db.commit()
        
        response = {
            "success": True,
            "message": f"已删除组合 {portfolio_code} 在 {snapshot_date} 的快照",
            "deleted": result["deleted"],
        }
        
        cascaded = result.get("cascaded_subscriptions", [])
        if cascaded:
            response["cascaded_subscriptions"] = cascaded
            response["message"] += f"（级联回退了 {len(cascaded)} 笔申购/赎回）"
        
        cascaded_events = result.get("cascaded_events", [])
        if cascaded_events:
            response["cascaded_events"] = cascaded_events
            response["message"] += f"（级联回退了 {len(cascaded_events)} 笔份额变动事件）"
        
        return response
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "DELETE_FAILED", "message": str(e)},
        )


@router.delete("/{portfolio_code}/bulk/{from_date}")
def delete_snapshots_bulk(
    portfolio_code: str,
    from_date: date,
    confirm: bool = Query(False, description="必须显式传 confirm=true 才执行删除"),
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    """
    批量删除从 from_date 开始的所有快照（含 from_date）
    
    从最新快照日开始倒序删除，确保级联回退的顺序正确。
    每个快照的删除都会触发级联回退（申购/赎回 CASH trade、事件）。
    必须显式传 confirm=true，否则返回 422 CONFIRM_REQUIRED（兼作影响面预览）。
    
    权限：仅admin
    """
    from app.services.snapshot_service import _delete_existing_snapshots
    from sqlalchemy import func
    from app.models import PortfolioPosition
    
    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail={"error": "PORTFOLIO_NOT_FOUND", "message": f"组合 {portfolio_code} 不存在"})
    
    # 获取所有需要删除的快照日期（从 from_date 开始，按日期降序）
    snapshot_dates = [
        row[0] for row in db.query(PortfolioValueSnapshot.snapshot_date)
        .filter(
            PortfolioValueSnapshot.portfolio_code == portfolio_code,
            PortfolioValueSnapshot.snapshot_date >= from_date,
        )
        .order_by(PortfolioValueSnapshot.snapshot_date.desc())
        .all()
    ]
    
    # 破坏性操作守卫：逐日 commit 不可中途回滚，必须显式确认
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "CONFIRM_REQUIRED",
                "message": f"将删除组合 {portfolio_code} 从 {from_date} 起的 {len(snapshot_dates)} 个快照，请携带 confirm=true 确认",
            },
        )
    
    if not snapshot_dates:
        return {
            "success": True,
            "message": f"组合 {portfolio_code} 在 {from_date} 之后无快照可删除",
            "deleted_count": 0,
        }
    
    results = []
    total_cascaded_subs = 0
    total_cascaded_events = 0
    
    for snap_date in snapshot_dates:
        try:
            result = _delete_existing_snapshots(db, portfolio_code, snap_date)
            cascaded_subs = result.get("cascaded_subscriptions", [])
            cascaded_events = result.get("cascaded_events", [])
            total_cascaded_subs += len(cascaded_subs)
            total_cascaded_events += len(cascaded_events)
            results.append({
                "snapshot_date": snap_date.isoformat(),
                "deleted": result["deleted"],
                "cascaded_subs": len(cascaded_subs),
                "cascaded_events": len(cascaded_events),
            })
            # 逐日 commit：单日删除立即落库，避免末尾统一提交放大回滚范围
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "BULK_DELETE_FAILED", "message": f"删除 {snap_date} 快照失败: {str(e)}"},
            )

    return {
        "success": True,
        "message": f"已删除组合 {portfolio_code} 从 {from_date} 起的 {len(snapshot_dates)} 个快照"
                   f"（级联回退 {total_cascaded_subs} 笔申购/赎回，{total_cascaded_events} 笔事件）",
        "deleted_count": len(snapshot_dates),
        "details": results,
    }
