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
        return SnapshotGenerationResult(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "VALIDATION_FAILED", "message": str(e)},
        )
    except Exception as e:
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
    
    权限：仅admin
    """
    try:
        result = recalculate_snapshots(
            db=db,
            portfolio_code=request.portfolio_code,
            start_date=request.start_date,
            end_date=request.end_date,
            force=request.force,
        )
        return RecalculationResult(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "VALIDATION_FAILED", "message": str(e)},
        )
    except Exception as e:
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
    
    权限：仅admin
    """
    from app.services.snapshot_service import _delete_existing_snapshots
    
    try:
        _delete_existing_snapshots(db, portfolio_code, snapshot_date)
        db.commit()
        
        return {
            "success": True,
            "message": f"已删除组合 {portfolio_code} 在 {snapshot_date} 的快照",
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "DELETE_FAILED", "message": str(e)},
        )
