"""issue #98 asset_classification 新增 asset_name 列并回填

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-06

1. 新增 asset_classification.asset_name 列（String(50)，可空）：
   聚合展示短名目（UI 分区/图例用），与 description（说明性文本）语义分工。

2. 存量 18 条种子分类按 code 回填 asset_name（映射内联于本文件）。

幂等设计：生产/CI 的启动顺序是先 `Base.metadata.create_all`（按当前模型
直接建出 asset_name 列），再从 base 执行 `alembic upgrade head`，因此迁移
到达本版本时列可能已存在。upgrade()/downgrade() 均先通过 inspector 检查
列存在性，仅在需要时执行 DDL（复用 0005 的 _existing_columns 模式）；
回填仅更新 asset_name IS NULL 的行，重跑无副作用，也不覆盖人工改过的值。

注意（#128）：原映射模块 app/constants/asset_names.py 已在维度重构中删除，
映射表内联回本迁移——历史迁移必须自包含，不引用可能被后续重构删除的应用代码。
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


# 原 app/constants/asset_names.py::ASSET_NAME_MAP（#98），#128 删除该模块后内联至此
ASSET_NAME_MAP: dict[str, str] = {
    "STOCK_CN_LARGE": "国内大盘",
    "STOCK_CN_SMALL": "国内中小盘",
    "STOCK_CN_VALUE": "国内价值",
    "STOCK_CN_GROWTH": "国内成长",
    "STOCK_CN_MIXED": "国内综合",
    "STOCK_HK_LARGE": "港股大盘",
    "STOCK_HK_SMALL": "港股中小盘",
    "STOCK_US": "美股",
    "STOCK_EU": "欧洲股票",
    "STOCK_JP": "日本股票",
    "STOCK_GLOBAL": "全球股票",
    "BOND_SHORT": "短债",
    "BOND_LONG": "中长债",
    "BOND_MIXED": "综合债",
    "BOND_US": "美债",
    "BOND_GLOBAL": "全球债券",
    "GOLD": "黄金",
    "CASH": "现金",
}


def _existing_columns(table: str) -> set:
    """实时查询表当前列名集合（每次新建 inspector，反映此前 DDL 的结果）"""
    inspector = sa.inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table)}


def upgrade():
    # 幂等：create_all 已按当前模型建出列则跳过 add_column
    if 'asset_name' not in _existing_columns('asset_classification'):
        op.add_column(
            'asset_classification',
            sa.Column('asset_name', sa.String(50), nullable=True),
        )

    # 回填存量行（仅补 NULL，幂等且不覆盖人工修改），纯 SQL 双方言通用
    for code, name in ASSET_NAME_MAP.items():
        op.execute(
            sa.text(
                "UPDATE asset_classification SET asset_name = :name "
                "WHERE code = :code AND asset_name IS NULL"
            ).bindparams(name=name, code=code)
        )


def downgrade():
    # 幂等：列存在才删除
    if 'asset_name' in _existing_columns('asset_classification'):
        op.drop_column('asset_classification', 'asset_name')
