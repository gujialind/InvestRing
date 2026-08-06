"""issue #98 asset_classification 新增 asset_name 列并回填

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-06

1. 新增 asset_classification.asset_name 列（String(50)，可空）：
   聚合展示短名目（UI 分区/图例用），与 description（说明性文本）语义分工
   见 app/constants/asset_names.py。

2. 存量 18 条种子分类按 code 回填 asset_name：
   映射单一事实来源为 app/constants/asset_names.py::ASSET_NAME_MAP，
   与 scripts/init_data.py 种子共用，杜绝两处手写漂移。

幂等设计：生产/CI 的启动顺序是先 `Base.metadata.create_all`（按当前模型
直接建出 asset_name 列），再从 base 执行 `alembic upgrade head`，因此迁移
到达本版本时列可能已存在。upgrade()/downgrade() 均先通过 inspector 检查
列存在性，仅在需要时执行 DDL（复用 0005 的 _existing_columns 模式）；
回填仅更新 asset_name IS NULL 的行，重跑无副作用，也不覆盖人工改过的值。
"""
from alembic import op
import sqlalchemy as sa

from app.constants.asset_names import ASSET_NAME_MAP


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


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
