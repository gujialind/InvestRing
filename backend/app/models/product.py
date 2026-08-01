from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey, func
from app.database import Base


class Product(Base):
    __tablename__ = "product"

    code = Column(String(20), primary_key=True)
    market = Column(String(20), primary_key=True, nullable=True)
    name = Column(String(100), nullable=False)
    product_type = Column(String(20), nullable=False)
    asset_class_code = Column(String(30), ForeignKey("asset_classification.code"))
    confirm_days = Column(Integer)
    is_qdii = Column(Boolean, default=False)
    data_source = Column(String(20), default="tushare")
    fallback_source = Column(String(20))
    data_source_status = Column(String(20), default="pending")
    last_sync_at = Column(DateTime)
    sync_error = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
