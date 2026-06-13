#!/usr/bin/env python3
"""
详细测试更新非净值资产 API（带完整错误追踪）
"""

import requests
import json
import sys
import os

# 添加 deps 目录到路径以使用 SQLAlchemy
sys.path.insert(0, 'deps')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 数据库配置
DB_CONFIG = {
    'host': 'rm-bp1627c6fp33q4ph42o.mysql.rds.aliyuncs.com',
    'port': 3306,
    'user': 'investring01',
    'password': 'InvestRing01',
    'database': 'investring',
}

DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset=utf8mb4"

# API 配置
API_BASE = "http://localhost:8000/api"

def check_prerequisites():
    """检查前置条件"""
    print("=" * 60)
    print("检查前置条件")
    print("=" * 60)
    
    # 1. 检查组合是否存在
    print("\n[1] 检查测试组合 PORT001 是否存在...")
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        from app.models.portfolio import Portfolio
        
        portfolio = db.query(Portfolio).filter(Portfolio.code == "PORT001").first()
        
        if portfolio:
            print(f"✓ 找到组合:")
            print(f"  代码: {portfolio.code}")
            print(f"  名称: {portfolio.name}")
            print(f"  状态: {portfolio.status}")
        else:
            print("✗ 组合 PORT001 不存在")
            print("  请先创建一个测试组合，或修改脚本中的组合代码")
            return False
        
        # 2. 检查平台是否存在
        print("\n[2] 检查平台 ZGYH 是否存在...")
        from app.models.platform import Platform
        
        platform = db.query(Platform).filter(Platform.code == "ZGYH").first()
        
        if platform:
            print(f"✓ 找到平台:")
            print(f"  代码: {platform.code}")
            print(f"  名称: {platform.name}")
        else:
            print("✗ 平台 ZGYH 不存在")
            print("  可用的平台列表:")
            platforms = db.query(Platform).all()
            for p in platforms:
                print(f"    - {p.code}: {p.name}")
            return False
        
        # 3. 检查 2024-12-17 是否为交易日
        print("\n[3] 检查 2024-12-17 是否为交易日...")
        from app.models.trading_calendar import TradingCalendar
        from datetime import date
        
        trading_day = db.query(TradingCalendar).filter(
            TradingCalendar.date == date(2024, 12, 17)
        ).first()
        
        if trading_day and trading_day.is_open:
            print(f"✓ 2024-12-17 是交易日")
        else:
            print(f"✗ 2024-12-17 不是交易日或不存在于数据库中")
            return False
        
        return True
        
    finally:
        db.close()

def login():
    """登录获取 token"""
    print("\n" + "=" * 60)
    print("登录获取 Token")
    print("=" * 60)
    
    response = requests.post(
        f"{API_BASE}/auth/login",
        json={
            "code": "admin",
            "password": "admin@2026"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("token")
        print(f"✓ 登录成功")
        print(f"  Token: {token[:50]}...")
        return token
    else:
        print(f"✗ 登录失败: {response.status_code}")
        print(f"  响应: {response.text}")
        return None

def test_update_cash(token):
    """测试更新非净值资产"""
    print("\n" + "=" * 60)
    print("测试更新非净值资产 API")
    print("=" * 60)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "amount": 100.0,
        "platform_code": "ZGYH",
        "update_date": "2024-12-17"
    }
    
    print(f"\n请求 URL: POST {API_BASE}/positions/portfolio/PORT001/cash-position")
    print(f"请求体: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{API_BASE}/positions/portfolio/PORT001/cash-position",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应内容类型: {response.headers.get('content-type')}")
        
        # 尝试解析响应
        if response.headers.get('content-type') == 'application/json':
            try:
                response_data = response.json()
                print(f"响应体 (JSON): {json.dumps(response_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"响应体 (原始): {response.text}")
        else:
            print(f"响应体 (原始): {response.text}")
        
        if response.status_code == 200:
            print("\n✓ API 调用成功！")
            return True
        elif response.status_code == 422:
            print("\n✗ 参数验证失败")
            try:
                error_data = response.json()
                print(f"  错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                pass
            return False
        elif response.status_code == 500:
            print("\n✗ 服务器内部错误 (500)")
            print("  可能原因:")
            print("  1. 数据库查询失败")
            print("  2. 组合/平台不存在")
            print("  3. 日期不是交易日")
            print("  4. 其他业务逻辑错误")
            print("\n  请查看后端终端输出获取详细错误信息")
            return False
        else:
            print(f"\n✗ API 调用失败 (HTTP {response.status_code})")
            return False
            
    except requests.exceptions.Timeout:
        print("\n✗ 请求超时")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"\n✗ 连接错误: {e}")
        return False
    except Exception as e:
        print(f"\n✗ 发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("开始详细测试...\n")
    
    # 1. 检查前置条件
    if not check_prerequisites():
        print("\n前置条件检查失败，测试终止")
        exit(1)
    
    # 2. 登录
    token = login()
    if not token:
        print("\n无法获取 token，测试终止")
        exit(1)
    
    # 3. 测试 API
    success = test_update_cash(token)
    
    print("\n" + "=" * 60)
    if success:
        print("✓ 测试通过！API 正常工作")
    else:
        print("✗ 测试失败！请检查上述错误信息")
        print("\n建议操作:")
        print("1. 查看后端终端输出的详细错误日志")
        print("2. 确认组合 PORT001 和平台 ZGYH 是否存在")
        print("3. 检查数据库中 2024-12-17 的交易日历记录")
    print("=" * 60)
    
    exit(0 if success else 1)
