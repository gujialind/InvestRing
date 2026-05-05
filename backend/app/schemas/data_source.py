from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DataSourceBase(BaseModel):
    name: str
    api_key: Optional[str] = None
    is_enabled: bool = True


class DataSourceUpdate(BaseModel):
    api_key: Optional[str] = None
    is_enabled: Optional[bool] = None


class DataSourceResponse(DataSourceBase):
    last_sync_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
