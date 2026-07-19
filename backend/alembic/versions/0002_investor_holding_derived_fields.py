"""investor_holding derived fields: market_value / total_cost / profit

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-18

Adds three nullable derived columns to investor_holding for #40 改进1.
Populated by _generate_investor_holding at snapshot time; historical
snapshots remain NULL (snapshots are append-only, no backfill script).
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    # 三列均 nullable，幂等加列（兼容 create_all 全新部署与老库迁移）
    for col_name, col in [
        ('market_value', sa.Column('market_value', sa.Numeric(15, 4), nullable=True)),
        ('total_cost', sa.Column('total_cost', sa.Numeric(15, 4), nullable=True)),
        ('profit', sa.Column('profit', sa.Numeric(15, 4), nullable=True)),
    ]:
        try:
            op.add_column('investor_holding', col)
        except Exception:
            pass


def downgrade():
    for col_name in ('profit', 'total_cost', 'market_value'):
        try:
            op.drop_column('investor_holding', col_name)
        except Exception:
            pass
