"""issue #144 组合级 display_config：持仓明细二级分组维度可配置

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-13

portfolio 表新增 display_config JSON 列（nullable，无回填）：
结构 {"ASSET_STOCK": "style", ...}，仅存显式覆盖项；NULL = 未配置 =
前端内置默认（股票→region、债券/商品→segment、现金平铺）。
校验以 asset_class_dimension_rule 规则表为权威来源（portfolio_service）。

幂等设计：add_column 用 try/except 兼容 create_all 已建列（同 0006 风格）；
被跳过时打 warning 日志，避免真实异常（连接失败/权限不足等）被静默吞掉。
sa.JSON 在 MySQL 8.4 为原生 JSON 类型、SQLite 存 TEXT，双方言兼容。
"""
import logging

from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade():
    # 幂等：兼容 create_all 已按模型建列
    try:
        op.add_column(
            'portfolio',
            sa.Column('display_config', sa.JSON(), nullable=True),
        )
    except Exception as exc:
        logger.warning("0010 跳过 portfolio.display_config 加列（可能已存在）: %s", exc)


def downgrade():
    op.drop_column('portfolio', 'display_config')
