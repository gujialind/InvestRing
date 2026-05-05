from sqlalchemy import Column, String, Text, DateTime, func
from app.database import Base


class Portfolio(Base):
    __tablename__ = "portfolio"

    code = Column(String(20), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    status = Column(String(20), default="draft")
    started_at = Column(DateTime)
    closed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
