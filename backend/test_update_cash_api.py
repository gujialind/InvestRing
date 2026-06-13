#!/usr/bin/env python3
"""
测试更新非净值资产 API
用于排查 Network Error 问题
"""

import requests
import json

# API 配置
API_BASE = "http://localhost:8000/api"

# 登录获取 token
def login():
    """使用 admin 账号登录获取 token"""
    response = requests.post(
        f"{API_BASE}/auth/login",
        json={
            "code": "admin",  # 使用 code 而不是 username
            "password": "admin@2026"  # 默认密码，可能需要修改
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        return data.get("token")
    else:
        print(f"✗ 登录失败: {response.status_code}")
        print(f"  响应: {response.text}")
        return None

# 测试更新非净值资产
def test_update_cash(token):
    """测试更新非净值资产 API"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 测试数据
    payload = {
        "amount": 100.0,
        "platform_code": "ZGYH",  # 中国银行
        "update_date": "2024-12-17"
    }
    
    print("=" * 60)
    print("测试更新非净值资产 API")
    print("=" * 60)
    print(f"\n请求 URL: {API_BASE}/positions/portfolio/PORT001/cash-position")
    print(f"请求方法: POST")
    print(f"请求头: {json.dumps(headers, indent=2)}")
    print(f"请求体: {json.dumps(payload, indent=2)}")
    print("\n发送请求...")
    
    try:
        response = requests.post(
            f"{API_BASE}/positions/portfolio/PORT001/cash-position",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应头: {json.dumps(dict(response.headers), indent=2)}")
        print(f"响应体: {response.text}")
        
        if response.status_code == 200:
            print("\n✓ API 调用成功！")
            return True
        else:
            print(f"\n✗ API 调用失败 (HTTP {response.status_code})")
            
            # 尝试解析错误信息
            try:
                error_data = response.json()
                print(f"  错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                pass
            
            return False
            
    except requests.exceptions.Timeout:
        print("\n✗ 请求超时")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"\n✗ 连接错误: {e}")
        print("  可能原因:")
        print("  1. 后端服务未启动")
        print("  2. CORS 配置阻止了请求")
        print("  3. 网络问题")
        return False
    except Exception as e:
        print(f"\n✗ 发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("开始测试...\n")
    
    # 1. 登录
    token = login()
    if not token:
        print("\n无法获取 token，测试终止")
        exit(1)
    
    print(f"\n✓ 登录成功，获取到 token")
    
    # 2. 测试 API
    success = test_update_cash(token)
    
    print("\n" + "=" * 60)
    if success:
        print("测试通过！API 正常工作")
    else:
        print("测试失败！请检查上述错误信息")
    print("=" * 60)
