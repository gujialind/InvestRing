/**
 * 前端 E2E 测试：回归守卫用例
 *
 * 本文件针对排查报告中已修复的 P0 问题设立回归防线，
 * 每个用例注明其防止复发的具体问题。
 */
import { test, expect, type Page, type Locator } from '@playwright/test';

/**
 * 进入组合列表并返回首个组合详情链接。
 * 组合列表为客户端 fetch，需等待渲染完成再判定空数据，
 * 否则首帧无链接会误判「没有组合数据」而错误 skip。
 */
async function gotoFirstPortfolio(page: Page): Promise<Locator> {
  await page.goto('/portfolio');
  const firstDetailLink = page.locator('a[href^="/portfolio/"]').first();
  try {
    await firstDetailLink.waitFor({ state: 'visible', timeout: 10_000 });
  } catch {
    test.skip(true, '环境中没有组合数据');
  }
  return firstDetailLink;
}

test.describe('页面渲染回归（防 P0 复发）', () => {
  // 防 P0-2：taskApi.list 返回分页对象却按数组处理，导致 tasks.map is not a function 白屏
  test('任务管理页应正常渲染，不出现客户端崩溃', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));

    await page.goto('/settings/tasks');

    await expect(page.getByRole('heading', { name: '任务管理' })).toBeVisible();
    // 用 heading 角色定位：「定时任务」文案同时出现在多个说明段落中，getByText 会 strict mode 违规
    await expect(page.getByRole('heading', { name: '定时任务' })).toBeVisible();
    // 执行历史区必须渲染（可以是空态，但不能是崩溃）
    await expect(page.getByText('执行历史')).toBeVisible();
    await expect(page.getByText(/Application error/i)).toHaveCount(0);
    expect(errors, `页面抛出未捕获异常: ${errors.join(' | ')}`).toHaveLength(0);
  });

  // 防 P0-7：侧边栏曾有指向不存在页面的「日志」死链
  test('侧边栏不应包含指向未实现页面的死链', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('aside a[href="/settings/logs"]')).toHaveCount(0);
  });

  // 防 P0-5：前端曾提供后端不存在的 DELETE /portfolios/{code}（405）
  test('组合详情页不应出现删除组合入口', async ({ page }) => {
    const firstDetailLink = await gotoFirstPortfolio(page);
    await firstDetailLink.click();
    await expect(page.getByRole('button', { name: '删除组合' })).toHaveCount(0);
  });
});

test.describe('移动端渲染回归（防 P0 复发）', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  // 防 P0-1：/m/login 曾被 m/layout 鉴权守卫拦截，渲染为空白导致移动端完全无法登录
  test('移动端登录页应渲染登录表单', async ({ page }) => {
    await page.goto('/m/login');
    await expect(page.getByLabel('用户名')).toBeVisible();
    await expect(page.getByLabel('密码')).toBeVisible();
    await expect(page.getByRole('button', { name: '登录' })).toBeVisible();
  });
});

test.describe('移动端布局回归（防 P0-8 复发）', () => {
  // 防 P0-8：/m 页面曾直接复用含 MainLayout 的 PC 页面，导致 PC 侧栏 + 底部 Tab 双导航
  test('移动端管理页不应出现 PC 侧边栏', async ({ page }) => {
    await page.goto('/m/products');
    // PC 侧边栏是 <aside>，移动端布局只应有 BottomNav（<nav>）
    await expect(page.locator('aside')).toHaveCount(0);
  });
});

test.describe('DateRangePicker 矮视口回归（防 #161 复发）', () => {
  // 防 #161：矮视口下日期区间弹层曾溢出视口、「确定」按钮不可达；
  // #161 以 max-h-[min(calc(100dvh_-_2rem),44rem)] + sticky footer 修复，
  // PR #164 修正 calc 任意值空格语法后高度兜底才真正生效——本用例以修正后行为为准。
  // 仅桌面项目有意义（mobile 项目 numberOfMonths=1、视口语义不同）
  test.use({ viewport: { width: 1280, height: 600 } });

  test('600px 视口下日期区间弹层「确定」按钮应在视口内可达', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', '矮视口断言仅针对桌面项目');

    const firstDetailLink = await gotoFirstPortfolio(page);
    // 详情页无「调仓交易」导航链接，从详情链接提取 code 直达 trades 子页（数据无关）
    const href = await firstDetailLink.getAttribute('href');
    await page.goto(`${href}/trades`);

    // DateRangePicker 触发器：默认区间「近1年」，按钮文案为 yyyy-MM-dd ~ yyyy-MM-dd
    await page.getByRole('button').filter({ hasText: '~' }).first().click();

    const confirmBtn = page.getByRole('button', { name: '确定' });
    await expect(confirmBtn).toBeVisible();
    const box = await confirmBtn.boundingBox();
    expect(box, '「确定」按钮未渲染出 boundingBox').not.toBeNull();
    if (box) {
      expect(box.y).toBeGreaterThanOrEqual(0);
      expect(box.y + box.height).toBeLessThanOrEqual(600);
    }
  });
});

test.describe('持仓明细维度二级分组（防 #109 / #114 复发，#128 维度化）', () => {
  // 防 #109：同分组产品曾各自独立成卡、无分组级合计；
  // 关系式断言（子分组头合计 = 名下各行市值之和），不硬绑定生产快照数字
  // V4 定稿 + #114 修正：分组 chip 始终位于产品名之上（与大类同名除外），
  // chip 行合计恒显示（无论名下 1 行还是多行）；
  // data-testid="asset-group-header" 挂在所有 chip 行上
  // #128：分组数据源从 asset_name 换成维度 name（股票→region、债券/商品→segment）
  test('子分组头合计金额应等于名下各行市值之和（含单行分组）', async ({ page }) => {
    const firstDetailLink = await gotoFirstPortfolio(page);
    await firstDetailLink.click();
    // 无快照/持仓数据的组合（如 draft）不渲染持仓明细区，此时无从断言，优雅 skip
    try {
      await page.getByText('持仓明细').waitFor({ state: 'visible', timeout: 10_000 });
    } catch {
      test.skip(true, '环境中组合无持仓明细数据（无快照/持仓）');
    }

    const headers = page.locator('[data-testid="asset-group-header"]');
    const headerCount = await headers.count();
    test.skip(
      headerCount === 0,
      '环境中无满足子分组 chip 渲染条件（组名与大类不同名）的数据'
    );

    // 金额均为「x,xxx.xx 元」格式，取文本内首个两位小数数字
    const firstAmount = (text: string) =>
      Number(text.replace(/\s+/g, ' ').match(/[\d,]+\.\d{2}/)?.[0].replace(/,/g, ''));

    for (let i = 0; i < headerCount; i++) {
      const header = headers.nth(i);
      const group = header.locator('xpath=ancestor::div[@data-testid="asset-group"]');
      const cards = group.locator('[data-testid="position-card"]');
      expect(await cards.count()).toBeGreaterThanOrEqual(1);

      const headerTotal = firstAmount(await header.innerText());
      let cardSum = 0;
      const cardCount = await cards.count();
      for (let j = 0; j < cardCount; j++) {
        cardSum += firstAmount(await cards.nth(j).innerText());
      }
      expect(headerTotal).toBeCloseTo(cardSum, 1);
    }
  });
});
