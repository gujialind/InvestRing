#!/usr/bin/env python3
"""
清理旧产品数据脚本
删除没有交易所后缀的旧产品代码，只保留带后缀的新产品
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from app.database import engine

def clean_old_products():
    """清理旧产品数据"""
    print("开始清理旧产品数据...")
    
    with engine.connect() as conn:
        # 删除没有交易所后缀的产品（除了 CASH）
        result = conn.execute(text("""
            DELETE FROM product 
            WHERE code NOT LIKE '%.SH' 
              AND code NOT LIKE '%.SZ' 
              AND code NOT LIKE '%.OF'
              AND code != 'CASH'
        """))
        conn.commit()
        deleted_count = result.rowcount
        print(f"已删除 {deleted_count} 条旧产品数据")

if __name__ == "__main__":
    clean_old_products()
    print("清理完成")
