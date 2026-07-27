from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_admin
from app.schemas.trading_calendar import (
    TradingCalendarResponse,
    TradingCalendarSyncRequest,
    TradingCalendarSyncResponse,
)
from app.services.trading_calendar_service import (
    sync_trading_calendar as sync_service,
    get_calendar_query,
    TushareNotConfiguredError,
    TushareAPIError,
)

router = APIRouter()


@router.get("", response_model=List[TradingCalendarResponse])
def get_trading_calendar(
    year: Optional[int] = Query(None, description="按年份过滤"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    is_open: Optional[bool] = Query(None, description="是否开盘"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    获取交易日历列表

    支持按年份、日期范围、是否开盘过滤
    """
    query = get_calendar_query(
        db=db,
        year=year,
        start_date=start_date,
        end_date=end_date,
        is_open=is_open,
    )
    return query.all()


@router.post("/sync", response_model=TradingCalendarSyncResponse)
def sync_trading_calendar(
    request: TradingCalendarSyncRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    同步指定年份的交易日历

    从 Tushare 获取交易日历数据并写入数据库
    """
    try:
        result = sync_service(db=db, year=request.year)
        # service 不 commit（AGENTS.md §4.1），事务边界在 router
        db.commit()
        return TradingCalendarSyncResponse(
            synced_count=result["synced_count"],
            year=result["year"],
            message="交易日历同步成功",
        )
    except TushareNotConfiguredError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "DATA_SOURCE_NOT_CONFIGURED", "message": str(e)},
        )
    except TushareAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "SYNC_FAILED", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "SYNC_FAILED", "message": f"同步失败: {str(e)}"},
        )
