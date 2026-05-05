from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class InvestorBase(BaseModel):
    code: str
    name: str
    role: str = "viewer"
    phone: Optional[str] = None
    email: Optional[str] = None


class InvestorCreate(InvestorBase):
    password: str


class InvestorUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class InvestorResponse(InvestorBase):
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
