"""sync_job table + nav_sync_detail job_id + HK fund fix

Revision ID: 0001
Revises:
Create Date: 2026-07-13

"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # sync_job — 使用 IF NOT EXISTS，兼容 create_all 已建表（全新部署）和 old-to-new 迁移
    op.execute("""
        CREATE TABLE IF NOT EXISTS sync_job (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            job_type VARCHAR(40) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            params JSON,
            total INTEGER DEFAULT 0,
            done INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            error_message TEXT,
            triggered_by VARCHAR(20) DEFAULT 'manual',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            started_at DATETIME,
            finished_at DATETIME
        )
    """)

    # index on sync_job — only if not already present
    try:
        op.create_index('ix_sync_job_status', 'sync_job', ['status'])
    except Exception:
        pass

    # nav_sync_detail columns — only if not already there (create_all on fresh DB already has them)
    for col_name, col in [
        ('job_id', sa.Column('job_id', sa.Integer(), nullable=True)),
        ('synced_count', sa.Column('synced_count', sa.Integer(), server_default='0')),
    ]:
        try:
            op.add_column('nav_sync_detail', col)
        except Exception:
            pass

    try:
        op.create_index('ix_nav_sync_detail_job_id', 'nav_sync_detail', ['job_id'])
    except Exception:
        pass

    try:
        op.create_foreign_key(
            'fk_nav_sync_detail_job_id', 'nav_sync_detail', 'sync_job',
            ['job_id'], ['id'],
        )
    except Exception:
        pass

    # HK_MUTUAL market/data_source fix (idempotent — no-op if no matching rows)
    op.execute(
        "UPDATE product SET market='HK_MUTUAL', data_source='akshare' "
        "WHERE code IN ('1001767344','1001767346') AND market='CN_OTC'"
    )


def downgrade():
    op.drop_constraint('fk_nav_sync_detail_job_id', 'nav_sync_detail', type_='foreignkey')
    op.drop_index('ix_nav_sync_detail_job_id', table_name='nav_sync_detail')
    op.drop_column('nav_sync_detail', 'synced_count')
    op.drop_column('nav_sync_detail', 'job_id')
    op.drop_index('ix_sync_job_status', table_name='sync_job')
    op.drop_table('sync_job')
