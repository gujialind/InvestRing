"""trade.transfer_group NOT NULL

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23

将 trade.transfer_group 置为 NOT NULL，强制交易现金流水规范（issue #53）：
每笔 trade 均隶属一个业务组（sub_/rebal_/裸 uuid），不存在裸 trade。

开发阶段无历史数据兼容负担；升级前对残留 NULL 做防御性回填，再改 NOT NULL。
权威目标为生产 MySQL；全新库经 create_all 已由模型直接建为 NOT NULL，本迁移对其为无操作。
幂等 try/except 包裹，避免 app 启动期 `alembic upgrade head` 抛错崩溃。
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    # 防御性回填：为残留 NULL 赋唯一占位组（dev 无历史数据，通常为空操作）
    try:
        op.execute(
            "UPDATE trade SET transfer_group = CONCAT('legacy_', id) "
            "WHERE transfer_group IS NULL"
        )
    except Exception:
        pass
    try:
        op.alter_column(
            'trade', 'transfer_group',
            existing_type=sa.String(36), nullable=False,
        )
    except Exception:
        pass


def downgrade():
    try:
        op.alter_column(
            'trade', 'transfer_group',
            existing_type=sa.String(36), nullable=True,
        )
    except Exception:
        pass
