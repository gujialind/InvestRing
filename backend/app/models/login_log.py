from sqlalchemy import Column, String, Text, DateTime, Integer, func
from app.database import Base


class LoginLog(Base):
    __tablename__ = "login_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    investor_code = Column(String(20), nullable=False)
    action = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    failure_reason = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
