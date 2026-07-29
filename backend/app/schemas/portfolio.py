from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime


class PortfolioBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class PortfolioCreate(PortfolioBase):
    pass


class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class PortfolioResponse(PortfolioBase):
    status: str = "draft"
    started_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PortfolioListItem(PortfolioResponse):
    """列表项：附聚合字段（issue #69），无快照时为 None/0。"""
    total_value: Optional[float] = None
    cumulative_return: Optional[float] = None
    investor_count: int = 0


class PaginatedPortfolioResponse(BaseModel):
    items: List[PortfolioListItem]
    total: int
    page: int
    page_size: int


class PortfolioValueSnapshotResponse(BaseModel):
    id: int
    portfolio_code: str
    snapshot_date: date
    total_value: float
    total_shares: float
    unit_price: float
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PortfolioInvestorItem(BaseModel):
    investor_code: str
    name: str
    shares: float


class NavHistoryRecord(BaseModel):
    snapshot_date: date
    unit_price: Optional[float] = None
    total_value: Optional[float] = None
    total_shares: Optional[float] = None
