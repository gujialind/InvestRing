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
    op.create_table(
        'sync_job',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('job_type', sa.String(40), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('total', sa.Integer(), server_default='0'),
        sa.Column('done', sa.Integer(), server_default='0'),
        sa.Column('success_count', sa.Integer(), server_default='0'),
        sa.Column('failed_count', sa.Integer(), server_default='0'),
        sa.Column('skipped_count', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('triggered_by', sa.String(20), server_default='manual'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_sync_job_status', 'sync_job', ['status'])

    op.add_column('nav_sync_detail', sa.Column('job_id', sa.Integer(), nullable=True))
    op.add_column('nav_sync_detail', sa.Column('synced_count', sa.Integer(), server_default='0'))
    op.create_index('ix_nav_sync_detail_job_id', 'nav_sync_detail', ['job_id'])
    op.create_foreign_key(
        'fk_nav_sync_detail_job_id', 'nav_sync_detail', 'sync_job',
        ['job_id'], ['id'],
    )

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
