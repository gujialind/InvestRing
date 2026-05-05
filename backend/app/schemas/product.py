from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ProductBase(BaseModel):
    code: str
    market: Optional[str] = None
    name: str
    product_type: str
    asset_class_code: Optional[str] = None
    confirm_days: int = 1
    is_qdii: bool = False


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    asset_class_code: Optional[str] = None
    confirm_days: Optional[int] = None
    is_qdii: Optional[bool] = None


class ProductResponse(ProductBase):
    data_source: Optional[str] = None
    data_source_status: str = "pending"
    last_sync_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
