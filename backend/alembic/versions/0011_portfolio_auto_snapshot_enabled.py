"""issue #156 组合级自动快照开关：portfolio.auto_snapshot_enabled

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-14

portfolio 表新增 auto_snapshot_enabled 布尔列（NOT NULL，默认 False，opt-in）：
仅约束自动任务（snapshot_generate 调度/手动触发），手动生成/重算端点不受影响。
存量组合回填为 False（server_default），需显式开启才纳入每日自动快照。

幂等设计：add_column 用 try/except 兼容 create_all 已建列（同 0010 风格）；
被跳过时打 warning 日志，避免真实异常（连接失败/权限不足等）被静默吞掉。
"""
import logging

from alembic import op
import sqlalchemy as sa


revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade():
    # 幂等：兼容 create_all 已按模型建列
    try:
        op.add_column(
            'portfolio',
            sa.Column(
                'auto_snapshot_enabled', sa.Boolean(),
                nullable=False, server_default=sa.text('0'),
            ),
        )
    except Exception as exc:
        logger.warning("0011 跳过 portfolio.auto_snapshot_enabled 加列（可能已存在）: %s", exc)


def downgrade():
    op.drop_column('portfolio', 'auto_snapshot_enabled')
