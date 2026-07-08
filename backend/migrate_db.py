#!/usr/bin/env python3
"""
数据库迁移脚本（测试环境）
直接重建表结构并初始化基础数据
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deps'))
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, engine
from app.models import (
    investor, portfolio, investor_holding, platform, product,
    asset_classification, portfolio_position, subscription, trade,
    price_record, share_change_event, portfolio_value_snapshot,
    trading_calendar, login_log, audit_log, scheduled_task,
    task_execution_log, nav_sync_detail, system_error_log, notification,
    idempotency_cache
)

print("=== 数据库迁移（测试环境） ===")
print("删除所有表...")
Base.metadata.drop_all(bind=engine)
print("所有表已删除")

print("\n创建所有表（含新 schema）...")
Base.metadata.create_all(bind=engine)
print("所有表已创建")

print("\n初始化基础数据...")
from scripts.init_data import (
    init_asset_classification, init_platforms, init_products,
    init_portfolios, init_scheduled_tasks, init_admin_user
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()
try:
    init_asset_classification(session)
    init_platforms(session)
    init_products(session)
    init_portfolios(session)
    init_scheduled_tasks(session)
    init_admin_user(session)
    print("\n=== 迁移完成 ===")
except Exception as e:
    print(f"\n迁移失败: {e}")
    session.rollback()
    raise
finally:
    session.close()
import sys
import json
sys.path.insert(0, ".")

from app.database import engine, Base, SessionLocal
from sqlalchemy import text, inspect
from app.models import *


def backup_data(db):
    data = {}

    r = db.execute(text("SELECT code, name, role, phone, email, password_hash, last_login_at, created_at, updated_at FROM investor"))
    data["investor"] = [dict(zip(r.keys(), row)) for row in r.fetchall()]

    r = db.execute(text("SELECT date, is_open, created_at FROM trading_calendar"))
    data["trading_calendar"] = [dict(zip(r.keys(), row)) for row in r.fetchall()]

    # 备份 subscription 表（含 platform_code，若字段不存在则置为 None）
    try:
        r = db.execute(text(
            "SELECT portfolio_code, investor_code, platform_code, sub_type, amount, shares, "
            "unit_price, apply_date, confirm_date, status, notes, created_at, updated_at "
            "FROM subscription"
        ))
        data["subscription"] = [dict(zip(r.keys(), row)) for row in r.fetchall()]
    except Exception:
        # 旧表可能没有 platform_code 字段
        r = db.execute(text(
            "SELECT portfolio_code, investor_code, sub_type, amount, shares, "
            "unit_price, apply_date, confirm_date, status, notes, created_at, updated_at "
            "FROM subscription"
        ))
        rows = [dict(zip(r.keys(), row)) for row in r.fetchall()]
        for row in rows:
            row["platform_code"] = None
        data["subscription"] = rows

    return data


def recreate_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("All tables recreated with new schema.")


def restore_data(db, data):
    if data.get("investor"):
        for row in data["investor"]:
            cols = ", ".join(row.keys())
            placeholders = ", ".join([f":{k}" for k in row.keys()])
            db.execute(text(f"INSERT INTO investor ({cols}) VALUES ({placeholders})"), row)

    if data.get("trading_calendar"):
        for row in data["trading_calendar"]:
            db.execute(text("INSERT INTO trading_calendar (date, is_open, created_at) VALUES (:date, :is_open, :created_at)"), row)

    # 恢复 subscription 数据，对历史无 platform_code 的记录填充默认值
    if data.get("subscription"):
        # 获取第一个平台作为默认值
        r = db.execute(text("SELECT code FROM platform LIMIT 1"))
        first_platform = r.fetchone()
        default_platform = first_platform[0] if first_platform else "DEFAULT"
        
        for row in data["subscription"]:
            if not row.get("platform_code"):
                row["platform_code"] = default_platform
            cols = ", ".join(row.keys())
            placeholders = ", ".join([f":{k}" for k in row.keys()])
            db.execute(text(f"INSERT INTO subscription ({cols}) VALUES ({placeholders})"), row)

    db.commit()
    sub_count = len(data.get("subscription", []))
    print(f"Restored {len(data.get('investor', []))} investors, {len(data.get('trading_calendar', []))} calendar entries, {sub_count} subscriptions.")


def main():
    db = SessionLocal()
    try:
        print("Backing up data...")
        data = backup_data(db)
        print(f"Backed up {len(data.get('investor', []))} investors, {len(data.get('trading_calendar', []))} calendar entries.")
    finally:
        db.close()

    recreate_database()

    db = SessionLocal()
    try:
        restore_data(db, data)
    finally:
        db.close()

    print("Migration complete!")


if __name__ == "__main__":
    main()
