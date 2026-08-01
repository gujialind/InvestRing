from sqlalchemy import Column, String, Numeric, DateTime, Integer, ForeignKey, func
from app.database import Base


class NavSyncDetail(Base):
    __tablename__ = "nav_sync_detail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_log_id = Column(Integer, ForeignKey("task_execution_log.id"))
    job_id = Column(Integer, ForeignKey("sync_job.id"), nullable=True, index=True)
    product_code = Column(String(20), nullable=False)
    market = Column(String(20), nullable=False)
    nav_date = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    nav_value = Column(Numeric(10, 4))
    synced_count = Column(Integer, default=0)
    source = Column(String(20))
    error_message = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())
