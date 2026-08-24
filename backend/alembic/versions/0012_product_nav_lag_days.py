"""issue #228 快照估值取价滞后天数：product.nav_lag_days

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-20

product 表新增 nav_lag_days 整数列（NOT NULL，默认 0）：快照估值取价滞后的
交易日数——0=取快照日当日净值/收盘价，N>0=取前第 N 个交易日净值。快照侧取价
一律由该列驱动，`is_qdii` 降级为纯展示标签（不再参与取价业务分支）；交易确认
侧仍恒取 T 日净值，不受本列影响。

回填口径：仅把存量**场外 QDII**（is_qdii=1 AND market='CN_OTC'）置 1，与
迁移前行为等价；互认基金（HK_MUTUAL）净值同样滞后一个交易日，但上线后由用户
经产品管理 UI / `ir product update --nav-lag-days 1` 手动置 1，不在此盲目回填。

幂等设计：add_column 用 try/except 兼容 create_all 已按模型建列（同 0011 风格），
被跳过时打 warning 日志，避免真实异常（连接失败/权限不足等）被静默吞掉；回填
UPDATE 用 bind 参数纯 SQL（SQLite/MySQL 双方言通用，同 0007），重复执行无副作用。
"""
import logging

from alembic import op
import sqlalchemy as sa


revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade():
    # 幂等：兼容 create_all 已按模型建列
    try:
        op.add_column(
            'product',
            sa.Column(
                'nav_lag_days', sa.Integer(),
                nullable=False, server_default=sa.text('0'),
            ),
        )
    except Exception as exc:
        logger.warning("0012 跳过 product.nav_lag_days 加列（可能已存在）: %s", exc)

    # 回填：仅场外 QDII 取 T-1（与迁移前行为等价）；互认基金上线后手动置 1
    op.execute(
        sa.text(
            "UPDATE product SET nav_lag_days = :lag "
            "WHERE is_qdii = :q AND market = :m"
        ).bindparams(lag=1, q=True, m='CN_OTC')
    )


def downgrade():
    op.drop_column('product', 'nav_lag_days')
