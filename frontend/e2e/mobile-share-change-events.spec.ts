/**
 * 前端 E2E 测试：移动端份额变动事件页（#276）
 *
 * 数据说明：种子环境不保证存在份额变动事件数据——列表断言兼容空态
 * （「暂无份额变动事件」），组合数据缺失时整组优雅 skip。
 * 仅 mobile project 有意义：/m 路由由 middleware 按 UA 重定向。
 */
import { test, expect, type Page } from '@playwright/test';

/** 进入首个组合的移动端详情页，返回组合 code */
async function gotoMobilePortfolioDetail(page: Page): Promise<string> {
  await page.goto('/portfolio');
  const firstDetailLink = page.locator('a[href*="/portfolio/"]').first();
  try {
    await firstDetailLink.waitFor({ state: 'visible', timeout: 10_000 });
  } catch {
    test.skip(true, '环境中没有组合数据');
  }
  const href = await firstDetailLink.getAttribute('href');
  const code = href!.split('/').filter(Boolean).pop()!;
  await page.goto(`/m/portfolio/${code}`);
  await expect(page.getByRole('heading', { name: '管理' })).toBeVisible({ timeout: 15_000 });
  return code;
}

test.describe('移动端份额变动事件页（#276）', () => {
  test('管理列表入口跳转并渲染列表/筛选', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile', '移动端入口断言仅针对移动项目');
    const errors: string[] = [];
    page.on('pageerror', (e) => {
      const msg = e.message;
      // 豁免 Next.js standalone/mobile 的 RSC `_rsc` prefetch 被 middleware 拦下的
      // 框架级 `access control` 噪音（同 product-select-market / platform-select-search spec 口径）
      if (/access control checks/.test(msg) && /_rsc=/.test(msg)) return;
      errors.push(msg);
    });

    const code = await gotoMobilePortfolioDetail(page);
    // 入口：页尾「管理」列表第 5 项
    await page.getByRole('link', { name: '份额变动事件' }).click();
    await expect(page).toHaveURL(`/m/portfolio/${code}/share-change-events`);

    // 页面骨架：标题 + 新建按钮 + 筛选折叠按钮（移动端形态）
    await expect(page.getByRole('heading', { name: '份额变动事件' })).toBeVisible();
    await expect(page.getByRole('button', { name: '新建事件' })).toBeVisible();
    await expect(page.getByRole('button', { name: '筛选' })).toBeVisible();
    // 列表渲染：事件行或空态二者必居其一
    await expect(
      page.getByText('暂无份额变动事件').or(page.locator('table tbody tr')).first()
    ).toBeVisible({ timeout: 15_000 });
    expect(errors, `页面抛出未捕获异常: ${errors.join(' | ')}`).toHaveLength(0);
  });

  test('筛选折叠面板展开显示控件', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile', '仅移动端项目');
    await gotoMobilePortfolioDetail(page);
    await page.getByRole('link', { name: '份额变动事件' }).click();
    await page.getByRole('button', { name: '筛选' }).waitFor({ timeout: 15_000 });

    // 折叠态：筛选控件不可见
    await expect(page.getByRole('combobox', { name: /全部状态|状态/ })).toHaveCount(0);
    await page.getByRole('button', { name: '筛选' }).click();
    // 展开态：状态/类型下拉与除息日区间出现
    await expect(page.getByText('全部状态')).toBeVisible();
    await expect(page.getByText('全部类型')).toBeVisible();
  });

  test('新建事件弹窗可打开（移动端单列表单）', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile', '仅移动端项目');
    await gotoMobilePortfolioDetail(page);
    await page.getByRole('link', { name: '份额变动事件' }).click();
    await page.getByRole('button', { name: '新建事件' }).waitFor({ timeout: 15_000 });

    await page.getByRole('button', { name: '新建事件' }).click();
    const dlg = page.locator('[role="dialog"]').filter({ hasText: '新建份额变动事件' }).first();
    await expect(dlg).toBeVisible();
    // 现金分红默认类型：每份分红金额字段存在
    await expect(dlg.getByText('每份分红金额（元）')).toBeVisible();
    await page.keyboard.press('Escape');
  });

  test('待确认事件编辑入口：列表名称展示与就地修改（#342，联动 #344 刷新）', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile', '仅移动端项目');
    const code = await gotoMobilePortfolioDetail(page);

    // API 造数：种子不保证有事件数据，经 REST 造一条 pending 现金分红事件；
    // 双日期取种子日历内固定交易日（2025-2026 工作日，见 seed_base）
    const token = await page.evaluate(() => localStorage.getItem('token'));
    if (!token) test.skip(true, '无法获取登录 token');
    const headers = { Authorization: `Bearer ${token}` };

    const products = await (await page.request.get('/api/products?page_size=1', { headers })).json();
    const platforms = await (await page.request.get('/api/platforms?page_size=1', { headers })).json();
    const product = products.items?.[0];
    const platform = platforms.items?.[0];
    if (!product || !platform) test.skip(true, '环境中没有产品/平台数据');

    const createResp = await page.request.post('/api/share-change-events', {
      headers,
      data: {
        portfolio_code: code,
        product_code: product.code,
        market: product.market,
        event_type: 'cash_dividend',
        ex_date: '2026-09-02',
        entitlement_date: '2026-09-01',
        platform_code: platform.code,
        div_cash: 0.5,
      },
    });
    if (!createResp.ok()) test.skip(true, `造数失败: ${createResp.status()} ${await createResp.text()}`);
    const created = await createResp.json();

    try {
      await page.getByRole('link', { name: '份额变动事件' }).click();

      // 列表展示（#342）：默认无日期筛选可见新事件；产品列「名称（代码）」
      const row = page.locator('table tbody tr').filter({ hasText: created.product_code }).first();
      await expect(row).toBeVisible({ timeout: 15_000 });
      if (product.name) {
        await expect(row.getByText(`${product.name}（${created.product_code}）`)).toBeVisible();
      }

      // pending 父记录有编辑入口
      await row.locator('button[title="编辑"]').click();
      const dlg = page.locator('[role="dialog"]').filter({ hasText: '编辑份额变动事件' }).first();
      await expect(dlg).toBeVisible();
      // 只读摘要含事件类型
      await expect(dlg.getByText('现金分红').first()).toBeVisible();

      // 修改每份分红金额并保存
      await dlg.locator('#edit_div_cash').fill('0.8');
      await dlg.getByRole('button', { name: '保存' }).click();
      await expect(dlg).toBeHidden();

      // 保存成功提示 + 行仍在（列表经 byPortfolio 失效即时刷新，无需手动刷新页面）
      await expect(page.getByText('更新成功')).toBeVisible();
      await expect(row).toBeVisible();
    } finally {
      await page.request.delete(`/api/share-change-events/${created.id}`, { headers });
    }
  });
});
