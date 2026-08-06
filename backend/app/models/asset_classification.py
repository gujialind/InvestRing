from sqlalchemy import Column, String, Text
from app.database import Base


class AssetClassification(Base):
    __tablename__ = "asset_classification"

    code = Column(String(30), primary_key=True, index=True)
    asset_type = Column(String(20), nullable=False)
    asset_category = Column(String(50), nullable=False)
    asset_subcat = Column(String(50))
    # 聚合展示短名目（UI 分区/图例用），与 description（说明性文本）语义分工见
    # app/constants/asset_names.py；存量行由迁移 0007 回填，回填前为 NULL
    asset_name = Column(String(50))
    description = Column(Text)
