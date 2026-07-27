from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from app.database import get_db
from app.schemas.market_data import PriceDataResponse, PriceDataSyncRequest
from app.services.market_data_service import (
    get_price_records,
    get_latest_price,
    sync_price_data,
    sync_portfolio_nav,
)

router = APIRouter()


@router.get("/products/{code}/{market}/price-data", response_model=List[PriceDataResponse])
def get_price_data(
    code: str,
    market: str,
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    limit: Optional[int] = Query(30, ge=1, le=365, description="限制返回数量"),
    db: Session = Depends(get_db),
):
    try:
        records = get_price_records(db, code, market, start_date, end_date, limit)
        return [
            PriceDataResponse(
                product_code=r.product_code,
                market=r.market,
                date=r.date,
                unit_price=float(r.unit_price),
            )
            for r in records
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询价格数据失败: {str(e)}")


@router.post("/products/{code}/{market}/sync-price-data")
def sync_price_data_endpoint(
    code: str,
    market: str,
    request: Optional[PriceDataSyncRequest] = None,
    db: Session = Depends(get_db),
):
    try:
        result = sync_price_data(
            db,
            code,
            market,
            start_date=request.start_date if request else None,
            end_date=request.end_date if request else None,
        )
        # service 不 commit（AGENTS.md §4.1）；在 success 判断前提交，
        # 保证 success=False 时 _mark_failed 写入的失败状态仍持久化
        db.commit()
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"同步价格数据失败: {str(e)}")


@router.post("/products/{code}/{market}/sync-history")
def sync_history(
    code: str,
    market: str,
    db: Session = Depends(get_db),
):
    end_date = date.today()

    try:
        result = sync_price_data(db, code, market, None, end_date)
        # 同 sync_price_data_endpoint：先提交再判 success，保留失败标记
        db.commit()
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"同步历史数据失败: {str(e)}")


@router.post("/portfolios/{portfolio_code}/sync-nav")
def sync_portfolio_nav_endpoint(
    portfolio_code: str,
    db: Session = Depends(get_db),
):
    try:
        result = sync_portfolio_nav(db, portfolio_code)
        if result["success"]:
            # service 不 commit（AGENTS.md §4.1），事务边界在 router
            db.commit()
            return result
        else:
            db.rollback()
            raise HTTPException(status_code=400, detail=result["message"])
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"同步组合净值失败: {str(e)}")
