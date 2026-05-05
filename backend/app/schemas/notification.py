from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NotificationBase(BaseModel):
    type: str
    level: str = "info"
    title: str
    content: Optional[str] = None
    recipient: Optional[str] = None
    channel: str = "in_app"


class NotificationCreate(NotificationBase):
    pass


class NotificationUpdate(BaseModel):
    status: Optional[str] = None


class NotificationResponse(NotificationBase):
    id: int
    status: str = "pending"
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
