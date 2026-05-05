from sqlalchemy import Column, String, Text
from app.database import Base


class AssetClassification(Base):
    __tablename__ = "asset_classification"

    code = Column(String(30), primary_key=True, index=True)
    asset_type = Column(String(20), nullable=False)
    asset_category = Column(String(50), nullable=False)
    asset_subcat = Column(String(50))
    description = Column(Text)
