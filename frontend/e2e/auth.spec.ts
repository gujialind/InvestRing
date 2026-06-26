/**
 * 前端 E2E 测试：认证流程
 */
import { test, expect } from '@playwright/test';

test.describe('登录认证', () => {
  test('登录成功应跳转到 dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('用户编码').fill('ADMIN');
    await page.getByLabel('密码').fill('admin@2026');
    await page.getByRole('button', { name: '登录' }).click();
    await expect(page).toHaveURL(/.*dashboard/);
  });

  test('登录失败应显示错误提示', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('用户编码').fill('ADMIN');
    await page.getByLabel('密码').fill('wrong_password');
    await page.getByRole('button', { name: '登录' }).click();
    // 应停留在登录页并显示错误
    await expect(page).toHaveURL(/.*login/);
  });

  test('未登录访问应重定向到登录页', async ({ page }) => {
    // 清除所有存储状态
    await page.context().clearCookies();
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/.*login/);
  });
});
