from sqlalchemy import Column, String, Text, DateTime, Integer, func
from app.database import Base


class SystemErrorLog(Base):
    __tablename__ = "system_error_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    error_type = Column(String(50), nullable=False)
    error_code = Column(String(50))
    error_message = Column(Text, nullable=False)
    error_stack = Column(Text)
    request_path = Column(String(200))
    request_method = Column(String(10))
    request_params = Column(Text)
    investor_code = Column(String(20))
    ip_address = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
