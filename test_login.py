#!/usr/bin/env python3
"""
InvestRing 登录功能测试脚本
使用 Playwright 测试登录页面的各项功能
"""

import sys
import time
import os

# 添加 skills 路径
sys.path.insert(0, '/data/user/skills/webapp-testing')

from playwright.sync_api import sync_playwright, expect

# 添加项目路径
sys.path.insert(0, '/workspace')
os.chdir('/workspace')

def test_login_page_loads(page):
    """测试登录页面是否正常加载"""
    print("=" * 50)
    print("测试 1: 登录页面加载")
    print("=" * 50)

    page.goto('http://localhost:3000/login')
    page.wait_for_load_state('networkidle')

    # 截图保存
    page.screenshot(path='/tmp/login_page.png', full_page=True)
    print("✓ 登录页面截图已保存到 /tmp/login_page.png")

    # 检查页面标题
    title = page.title()
    print(f"✓ 页面标题: {title}")

    # 检查关键元素是否存在
    try:
        # 尝试找到用户名输入框
        username_input = page.locator('input[type="text"], input[name="username"], input[name="code"]').first
        expect(username_input).to_be_visible()
        print("✓ 用户名输入框存在")

        # 尝试找到密码输入框
        password_input = page.locator('input[type="password"]').first
        expect(password_input).to_be_visible()
        print("✓ 密码输入框存在")

        # 尝试找到登录按钮
        login_button = page.locator('button[type="submit"], button:has-text("登录")').first
        expect(login_button).to_be_visible()
        print("✓ 登录按钮存在")

    except Exception as e:
        print(f"✗ 页面元素检查失败: {e}")
        page.screenshot(path='/tmp/login_page_error.png', full_page=True)
        raise

    print()
    return True


def test_login_with_valid_credentials(page):
    """测试使用有效凭据登录"""
    print("=" * 50)
    print("测试 2: 使用有效凭据登录")
    print("=" * 50)

    page.goto('http://localhost:3000/login')
    page.wait_for_load_state('networkidle')

    # 找到输入框
    try:
        # 尝试多种选择器
        username_input = None
        for selector in ['input[name="code"]', 'input[placeholder*="用户名"]', 'input[placeholder*="账号"]', 'input[type="text"]']:
            try:
                username_input = page.locator(selector).first
                if username_input.is_visible():
                    print(f"✓ 找到用户名输入框 (selector: {selector})")
                    break
            except:
                continue

        if not username_input or not username_input.is_visible():
            print("✗ 未找到用户名输入框")
            page.screenshot(path='/tmp/login_no_input.png', full_page=True)
            return False

        password_input = page.locator('input[type="password"]').first
        print("✓ 找到密码输入框")

        # 输入凭据 - 使用默认测试账号
        username_input.fill('admin')
        password_input.fill('admin123')
        print("✓ 已填写凭据 (admin/admin123)")

        # 点击登录按钮
        login_button = page.locator('button[type="submit"]').first
        login_button.click()
        print("✓ 已点击登录按钮")

        # 等待响应
        page.wait_for_load_state('networkidle')
        time.sleep(2)

        # 检查是否登录成功（跳转到 dashboard）
        current_url = page.url
        print(f"✓ 当前 URL: {current_url}")

        if '/dashboard' in current_url or '/login' not in current_url:
            print("✓ 登录成功，跳转到仪表盘")
            page.screenshot(path='/tmp/login_success.png', full_page=True)
            return True
        else:
            print("✗ 登录可能失败，仍在登录页")
            page.screenshot(path='/tmp/login_failed.png', full_page=True)

            # 检查是否有错误提示
            try:
                error_msg = page.locator('text=/错误|失败|密码|账号/i').first
                if error_msg.is_visible():
                    print(f"✓ 发现错误提示: {error_msg.text_content()}")
            except:
                pass

            return False

    except Exception as e:
        print(f"✗ 登录测试失败: {e}")
        page.screenshot(path='/tmp/login_exception.png', full_page=True)
        return False

    print()
    return False


def test_login_with_invalid_credentials(page):
    """测试使用无效凭据登录"""
    print("=" * 50)
    print("测试 3: 使用无效凭据登录")
    print("=" * 50)

    page.goto('http://localhost:3000/login')
    page.wait_for_load_state('networkidle')

    try:
        # 找到输入框
        username_input = page.locator('input[name="code"], input[type="text"]').first
        password_input = page.locator('input[type="password"]').first

        # 输入错误凭据
        username_input.fill('wronguser')
        password_input.fill('wrongpass')
        print("✓ 已填写错误凭据")

        # 点击登录按钮
        login_button = page.locator('button[type="submit"]').first
        login_button.click()
        print("✓ 已点击登录按钮")

        # 等待响应
        time.sleep(2)
        page.wait_for_load_state('networkidle')

        # 检查是否显示错误提示
        current_url = page.url
        if '/login' in current_url:
            print("✓ 仍在登录页（预期行为）")

            # 检查错误消息
            try:
                # 尝试多种错误提示选择器
                error_selectors = [
                    '[role="alert"]',
                    '.text-red',
                    '[class*="error"]',
                    'text=/错误|失败|密码|账号.*不正确/i'
                ]
                for selector in error_selectors:
                    try:
                        error_elem = page.locator(selector).first
                        if error_elem.is_visible():
                            error_text = error_elem.text_content()
                            print(f"✓ 发现错误提示: {error_text}")
                            break
                    except:
                        continue
            except Exception as e:
                print(f"  (未发现明确的错误提示元素)")

            page.screenshot(path='/tmp/login_invalid_success.png', full_page=True)
            print("✓ 无效凭据测试通过（正确拒绝登录）")
            return True
        else:
            print("✗ 错误：使用无效凭据竟然登录成功！")
            page.screenshot(path='/tmp/login_invalid_hack.png', full_page=True)
            return False

    except Exception as e:
        print(f"✗ 无效凭据测试异常: {e}")
        page.screenshot(path='/tmp/login_invalid_exception.png', full_page=True)
        return False

    print()
    return True


def test_logout(page):
    """测试登出功能"""
    print("=" * 50)
    print("测试 4: 登出功能")
    print("=" * 50)

    # 先登录
    page.goto('http://localhost:3000/login')
    page.wait_for_load_state('networkidle')

    try:
        username_input = page.locator('input[name="code"], input[type="text"]').first
        password_input = page.locator('input[type="password"]').first
        username_input.fill('admin')
        password_input.fill('admin123')

        login_button = page.locator('button[type="submit"]').first
        login_button.click()
        page.wait_for_load_state('networkidle')
        time.sleep(2)

        # 检查是否已登录
        if '/dashboard' not in page.url and '/login' in page.url:
            print("✗ 登录失败，无法测试登出")
            return False

        print("✓ 已登录到系统")

        # 查找登出按钮
        logout_selectors = [
            'button:has-text("退出")',
            'button:has-text("登出")',
            'button:has-text("Logout")',
            '[aria-label="logout"]',
            '[data-testid="logout"]'
        ]

        logout_found = False
        for selector in logout_selectors:
            try:
                logout_btn = page.locator(selector).first
                if logout_btn.is_visible():
                    print(f"✓ 找到登出按钮 (selector: {selector})")
                    logout_btn.click()
                    logout_found = True
                    break
            except:
                continue

        if not logout_found:
            print("⚠ 未在页面上找到明显的登出按钮（可能需要点击用户菜单）")
            # 尝试点击用户头像或菜单
            try:
                user_menu = page.locator('[aria-label="menu"], [aria-label="user"], button:has(svg)').first
                user_menu.click()
                time.sleep(1)

                # 再找登出按钮
                for selector in logout_selectors:
                    try:
                        logout_btn = page.locator(selector).first
                        if logout_btn.is_visible():
                            logout_btn.click()
                            logout_found = True
                            break
                    except:
                        continue
            except:
                pass

        if logout_found:
            page.wait_for_load_state('networkidle')
            time.sleep(1)

            if '/login' in page.url:
                print("✓ 登出成功，跳转回登录页")
                page.screenshot(path='/tmp/logout_success.png', full_page=True)
                return True
            else:
                print("⚠ 登出后未跳转回登录页")
                return False
        else:
            print("⚠ 无法测试登出功能（未找到登出按钮）")
            return False

    except Exception as e:
        print(f"✗ 登出测试异常: {e}")
        page.screenshot(path='/tmp/logout_exception.png', full_page=True)
        return False

    print()
    return True


def test_console_errors(page):
    """检查控制台错误"""
    print("=" * 50)
    print("测试 5: 控制台错误检查")
    print("=" * 50)

    console_errors = []

    def handle_console(msg):
        if msg.type == 'error':
            console_errors.append(msg.text)

    page.on('console', handle_console)

    page.goto('http://localhost:3000/login')
    page.wait_for_load_state('networkidle')
    time.sleep(2)

    # 尝试登录
    try:
        username_input = page.locator('input[name="code"], input[type="text"]').first
        password_input = page.locator('input[type="password"]').first
        username_input.fill('admin')
        password_input.fill('admin123')
        page.locator('button[type="submit"]').first.click()
        page.wait_for_load_state('networkidle')
        time.sleep(2)
    except:
        pass

    if console_errors:
        print(f"✗ 发现 {len(console_errors)} 个控制台错误:")
        for i, err in enumerate(console_errors, 1):
            print(f"  {i}. {err[:100]}...")
        return False
    else:
        print("✓ 无控制台错误")
        return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("InvestRing 登录功能测试")
    print("=" * 60 + "\n")

    results = {
        'login_page_loads': False,
        'login_valid': False,
        'login_invalid': False,
        'logout': False,
        'console_errors': False
    }

    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            locale='zh-CN'
        )
        page = context.new_page()

        try:
            # 执行各项测试
            results['login_page_loads'] = test_login_page_loads(page)
            results['login_valid'] = test_login_with_valid_credentials(page)
            results['login_invalid'] = test_login_with_invalid_credentials(page)
            results['logout'] = test_logout(page)
            results['console_errors'] = test_console_errors(page)

        except Exception as e:
            print(f"\n✗ 测试执行异常: {e}")
            import traceback
            traceback.print_exc()

        finally:
            browser.close()

    # 打印测试结果汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        test_display_name = {
            'login_page_loads': '登录页面加载',
            'login_valid': '有效凭据登录',
            'login_invalid': '无效凭据登录',
            'logout': '登出功能',
            'console_errors': '控制台错误'
        }.get(test_name, test_name)

        print(f"  {test_display_name}: {status}")

    passed_count = sum(results.values())
    total_count = len(results)
    print(f"\n通过率: {passed_count}/{total_count} ({passed_count*100//total_count}%)")

    # 返回退出码
    sys.exit(0 if all(results.values()) else 1)


if __name__ == '__main__':
    main()
