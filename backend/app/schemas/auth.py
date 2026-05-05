from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    code: str
    password: str


class UserInfo(BaseModel):
    code: str
    name: str
    role: str


class LoginResponse(BaseModel):
    token: str
    expires_at: str
    user: UserInfo


class ChangePasswordRequest(BaseModel):
    target_code: Optional[str] = None
    old_password: Optional[str] = None
    new_password: str
