from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class AssetClassification(Base):
    """资产分类维度值字典（issue #128 正交维度重构）。

    每行是一个维度值：dimension 区分所属维度（asset_class/region/style/size/segment），
    code 形如 `维度前缀_语义词`（ASSET_STOCK/REGION_CN/STYLE_GROWTH/SIZE_LARGE/SEG_GOLD）。
    name 为聚合展示名目（UI 分区/图例/二级分组用）；asset_class 维度的 sort_order
    同时是前端色板序位，变更即改色。维度值字典单一事实来源见
    app/constants/asset_dimensions.py。
    """
    __tablename__ = "asset_classification"

    code = Column(String(30), primary_key=True, index=True)
    dimension = Column(String(20), nullable=False)
    name = Column(String(50), nullable=False)
    sort_order = Column(Integer, default=0)
    description = Column(Text)
