from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LoginLogResponse(BaseModel):
    id: int
    investor_code: str
    action: Optional[str] = None
    status: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: int
    investor_code: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SystemErrorLogResponse(BaseModel):
    id: int
    error_type: str
    error_code: Optional[str] = None
    error_message: str
    error_stack: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    request_params: Optional[str] = None
    investor_code: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
