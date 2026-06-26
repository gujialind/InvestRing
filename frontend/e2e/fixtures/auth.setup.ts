/**
 * Playwright 认证 Setup
 * 登录一次，保存 auth state 供所有测试复用
 */
import { test as setup } from '@playwright/test';

const ADMIN_AUTH_FILE = 'e2e/.auth/admin.json';

setup('以管理员身份登录并保存状态', async ({ page }) => {
  // 访问登录页
  await page.goto('/login');

  // 填写登录表单
  await page.getByLabel('用户编码').fill('ADMIN');
  await page.getByLabel('密码').fill('admin123');

  // 提交登录
  await page.getByRole('button', { name: '登录' }).click();

  // 等待跳转到 dashboard
  await page.waitForURL('**/dashboard', { timeout: 10_000 });

  // 保存认证状态
  await page.context().storageState({ path: ADMIN_AUTH_FILE });
});
