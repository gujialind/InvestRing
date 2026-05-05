from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PlatformBase(BaseModel):
    code: str
    name: str
    platform_type: Optional[str] = None


class PlatformCreate(PlatformBase):
    pass


class PlatformUpdate(BaseModel):
    name: Optional[str] = None
    platform_type: Optional[str] = None


class PlatformResponse(PlatformBase):
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
