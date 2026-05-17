#!/usr/bin/env python3
import sys
import os

# 添加项目路径和依赖路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'deps'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, engine
from app.models.investor import Investor

print("=== 检查数据库 ===")

# 检查是否有表
print("\n1. 检查 Investor 表...")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    investors = db.query(Investor).all()
    print(f"   找到 {len(investors)} 个用户:")
    for inv in investors:
        print(f"   - 代码: {inv.code}, 姓名: {inv.name}, 角色: {inv.role}")
    if not investors:
        print("   ⚠️  没有找到任何用户！")
        
except Exception as e:
    print(f"   ❌ 错误: {e}")
    import traceback
    traceback.print_exc()

db.close()
