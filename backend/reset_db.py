#!/usr/bin/env python3
"""
重置数据库脚本 - 删除所有表并重新创建
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from app.database import Base, engine
from app.models import (
    investor, portfolio, investor_holding, platform, product, 
    asset_classification, portfolio_position, subscription, trade,
    price_record, share_change_event, portfolio_value_snapshot,
    trading_calendar, login_log, audit_log, scheduled_task,
    task_execution_log, nav_sync_detail, system_error_log, notification,
    idempotency_cache
)

print("=== 开始重置数据库 ===")
print("删除所有表...")
Base.metadata.drop_all(bind=engine)
print("所有表已删除")
print("\n创建所有表...")
Base.metadata.create_all(bind=engine)
print("所有表已创建")
print("\n=== 数据库重置完成 ===")
