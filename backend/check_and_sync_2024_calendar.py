#!/usr/bin/env python3
"""
检查并同步 2024 年交易日历数据
用于解决更新非净值资产时的"Network Error"问题
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date

# 导入项目模块
from app.models.trading_calendar import TradingCalendar
from app.services.tushare_client import get_trade_calendar

# 数据库配置
DB_CONFIG = {
    'host': 'rm-bp1627c6fp33q4ph42o.mysql.rds.aliyuncs.com',
    'port': 3306,
    'user': 'investring01',
    'password': 'InvestRing01',
    'database': 'investring',
}

DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset=utf8mb4"

def main():
    print("=" * 60)
    print("检查并同步 2024 年交易日历数据")
    print("=" * 60)

    # 创建数据库连接
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # 1. 检查 2024-12-17 是否在数据库中
        print("\n[1] 检查 2024-12-17 是否在数据库中...")
        trading_day = db.query(TradingCalendar).filter(
            TradingCalendar.date == date(2024, 12, 17)
        ).first()

        if trading_day:
            print(f"✓ 找到记录:")
            print(f"  日期: {trading_day.date}")
            print(f"  是否交易日: {'是' if trading_day.is_open else '否'}")
            print(f"  创建时间: {trading_day.created_at}")
        else:
            print("✗ 数据库中不存在 2024-12-17 的记录")

        # 2. 检查 2024 年全年有多少条记录
        print("\n[2] 检查 2024 年全年交易日历数据...")
        year_2024_count = db.query(TradingCalendar).filter(
            TradingCalendar.date >= date(2024, 1, 1),
            TradingCalendar.date <= date(2024, 12, 31)
        ).count()

        print(f"  2024 年已有记录数: {year_2024_count}")

        # 3. 从 Tushare 获取 2024 年交易日历
        print("\n[3] 从 Tushare 获取 2024 年交易日历...")
        try:
            calendar_data = get_trade_calendar(2024)
            if calendar_data:
                print(f"✓ 成功获取 {len(calendar_data)} 条记录")

                # 统计交易日数量
                trading_days = sum(1 for item in calendar_data if item["is_open"])
                print(f"  其中交易日: {trading_days} 天")
                print(f"  非交易日: {len(calendar_data) - trading_days} 天")
            else:
                print("✗ 未获取到数据，请检查 TUSHARE_TOKEN 配置")
                return
        except Exception as e:
            print(f"✗ 获取 Tushare 数据失败: {e}")
            return

        # 4. 找出需要插入的记录
        print("\n[4] 找出需要插入的记录...")
        existing_dates = {
            row[0] for row in db.query(TradingCalendar.date)
            .filter(
                TradingCalendar.date >= date(2024, 1, 1),
                TradingCalendar.date <= date(2024, 12, 31)
            )
            .all()
        }

        new_records = []
        for item in calendar_data:
            item_date = date.fromisoformat(item["date"])
            if item_date not in existing_dates:
                new_records.append({
                    "date": item_date,
                    "is_open": item["is_open"],
                })

        print(f"  需要插入的记录数: {len(new_records)}")

        # 5. 插入新记录
        if new_records:
            print("\n[5] 插入新记录...")
            db.bulk_insert_mappings(TradingCalendar, new_records)
            db.commit()
            print(f"✓ 成功插入 {len(new_records)} 条记录")

            # 验证 2024-12-17 是否已存在
            print("\n[6] 验证 2024-12-17...")
            trading_day = db.query(TradingCalendar).filter(
                TradingCalendar.date == date(2024, 12, 17)
            ).first()

            if trading_day:
                print(f"✓ 2024-12-17 已成功插入:")
                print(f"  日期: {trading_day.date}")
                print(f"  是否交易日: {'是' if trading_day.is_open else '否'}")
            else:
                print("✗ 2024-12-17 仍未找到，可能插入失败")
        else:
            print("\n[5] 无需插入新记录")

        print("\n" + "=" * 60)
        print("完成！现在可以重新尝试更新非净值资产操作")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
