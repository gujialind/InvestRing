/**
 * 前端 E2E 测试：认证流程
 */
import { test, expect } from '@playwright/test';

test.describe('登录认证', () => {
  // 本组用例需从未登录态开始，不复用 setup 保存的 storageState
  test.use({ storageState: { cookies: [], origins: [] } });

  test('登录成功应跳转到 dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('用户名').fill('ADMIN');
    await page.getByLabel('密码').fill('admin@2026');
    await page.getByRole('button', { name: '登录' }).click();
    await expect(page).toHaveURL(/dashboard/);
  });

  test('登录失败应停留在登录页', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('用户名').fill('ADMIN');
    await page.getByLabel('密码').fill('wrong_password');
    await page.getByRole('button', { name: '登录' }).click();
    await expect(page).toHaveURL(/login/);
  });

  test('未登录访问受保护页应重定向到登录页', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/login/);
  });
});
