import { defineConfig, devices } from '@playwright/test';

/**
 * InvestRing 前端 E2E 测试配置
 *
 * 运行方式：
 *   npx playwright test              # 运行所有测试
 *   npx playwright test --project=chromium  # 仅桌面端
 *   npx playwright test --project=mobile    # 仅移动端
 *   npx playwright test --ui          # 交互式 UI 模式
 *   npx playwright test --debug       # 调试模式
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },

  // CI 中失败自动重试 2 次
  retries: process.env.CI ? 2 : 0,

  // 并行执行
  fullyParallel: true,
  workers: process.env.CI ? 1 : undefined,

  // 报告器
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
  },

  // 自动启动开发服务器
  webServer: {
    command: 'npm run dev',
    port: 3000,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },

  projects: [
    // 认证状态设置（登录一次，所有测试共享）
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
    },
    // 桌面端 Chrome
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/admin.json',
      },
      dependencies: ['setup'],
    },
    // 移动端（chromium 内核）：原用 iPhone 13（webkit 内核），
    // 但 webkit 下登录成功后 /dashboard→/m/dashboard 的 307 跳转会被取消
    // （浏览器侧 "Load request cancelled"，真实原因未定位），改用同为移动
    // 视口的 Pixel 5（chromium），与 CI 只装 chromium 保持一致
    {
      name: 'mobile',
      use: {
        ...devices['Pixel 5'],
        storageState: 'e2e/.auth/admin.json',
      },
      dependencies: ['setup'],
    },
  ],
});
