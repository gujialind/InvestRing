from sqlalchemy import Column, String, Text, DateTime, Integer, func
from app.database import Base


class TaskExecutionLog(Base):
    __tablename__ = "task_execution_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_code = Column(String(50), nullable=False)
    trigger_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration_ms = Column(Integer)
    records_total = Column(Integer)
    records_success = Column(Integer)
    records_failed = Column(Integer)
    error_message = Column(Text)
    error_stack = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
