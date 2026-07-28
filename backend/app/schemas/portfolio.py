from pydantic import BaseModel
from typing import Optional
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


class NavHistoryRecord(BaseModel):
    snapshot_date: date
    unit_price: Optional[float] = None
    total_value: Optional[float] = None
    total_shares: Optional[float] = None
