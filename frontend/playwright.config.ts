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
    // 路由预热：先编译 E2E 涉及的全部路由（next dev 按需编译会向已连接
    // 客户端广播重建、触发 full reload 取消其他客户端进行中的导航，
    // 即 PR #169 「webkit 307 跳转被取消」的根因，详见 fixtures/warmup.ts）
    {
      name: 'warmup',
      testMatch: /warmup\.ts/,
    },
    // 认证状态设置（登录一次，所有测试共享）
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
      dependencies: ['warmup'],
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
    // 移动端 webkit（iPhone 13）：PR #169 曾困「登录后 /dashboard→/m/dashboard
    // 307 跳转被取消（Load request cancelled）」改用 Pixel 5（chromium）绕过，
    // 后续实测定位到两个与 webkit 无关的 dev 竞态（根因，均已修复）：
    //   1. next dev 重编译触发的 Fast Refresh full reload 会取消进行中的导航；
    //   2. hydration 前 fill 的值被 controlled input 重渲染清空，登录静默失败
    //      （JS 较慢的引擎先触发）——auth.setup.ts/auth.spec.ts 已加水合等待
    {
      name: 'mobile',
      use: {
        ...devices['iPhone 13'],
        storageState: 'e2e/.auth/admin.json',
      },
      dependencies: ['setup'],
    },
  ],
});
