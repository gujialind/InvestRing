/**
 * 前端 E2E 测试：提交交易产品选择器市场标识（防 #259 回归）
 *
 * 守护 SearchableProductSelect 的市场标识契约（LOF 一码双市场分行）：
 *   - 搜 161017 → 161017.SZ / 161017.OF 两条选项分行；名称 / (code) / 市场 Badge
 *     三段各自独立元素，长名称截断不挤掉 (code) 与市场标识；两行市场文案不同
 *     （A股场内 / 内地场外），场内场外可分辨；
 *   - 选项行 title 悬停给出完整「名称 (code) · 市场」；
 *   - 选中场外项 → 弹层关闭，触发按钮回显「名称 (code) · 市场名」并挂 title 全文本。
 *
 * 定位器契约（沿用 platform-select-search.spec.ts 的 #217 惯例）：选项行
 * data-testid="product-option" + data-code/data-market 属性定位（一码多市场时
 * 单靠 code 不唯一，须 code+market 双属性），不解析文案取 code、不依赖 Tailwind
 * 工具类与 Badge/lucide 内部结构；触发按钮 aria-haspopup="dialog" + 文本双条件。
 * 市场 Badge / 回显文本断言保留——那是用户可见契约，不是实现耦合。
 *
 * 数据说明：依赖 seed_base.py 的 161017.SZ/161017.OF LOF 双市场种子（#259）；
 * 无种子/无组合数据时优雅 skip，不在 CI 造数据。双端复跑：TradesContent 为共享
 * 组件（「提交交易」Dialog 双端同构），mobile project 自动覆盖，无需单独用例。
 */
import { test, expect, type Page, type Locator } from '@playwright/test';

/** LOF 双市场种子常量（与 backend/tests/seed_base.py 的 #259 种子一致） */
const LOF_NAME = '富国中证500指数增强(LOF)A';
const LOF_SZ = { code: '161017.SZ', market: 'CN_EXCHANGE', marketName: 'A股场内' };
const LOF_OTC = { code: '161017.OF', market: 'CN_OTC', marketName: '内地场外' };

/** 收集页面未捕获异常（客户端崩溃防线），用例末尾断言为空 */
function collectPageErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  return errors;
}

/** 进入组合列表，返回首个组合详情页路径（mobile project 经 middleware 重定向拿到 /m 前缀路径） */
async function firstPortfolioHref(page: Page): Promise<string> {
  await page.goto('/portfolio');
  const firstDetailLink = page.locator('a[href*="/portfolio/"]').first();
  try {
    await firstDetailLink.waitFor({ state: 'visible', timeout: 10_000 });
  } catch {
    test.skip(true, '环境中没有组合数据');
  }
  const href = await firstDetailLink.getAttribute('href');
  if (!href) throw new Error('组合详情链接缺少 href');
  return href;
}

/** 按弹窗标题定位业务 Dialog（Popover 弹层同样带 role=dialog，需用文案区分） */
function dialogByTitle(page: Page, title: string | RegExp): Locator {
  return page.locator('[role="dialog"]').filter({ hasText: title }).first();
}

/** 进入首个组合的调仓交易页并打开「提交交易」Dialog（双端共享，无需按 project 区分） */
async function openSubmitTradeDialog(page: Page): Promise<Locator> {
  const href = await firstPortfolioHref(page);
  await page.goto(`${href}/trades`);
  await page.getByRole('button', { name: '提交交易' }).first().waitFor({ timeout: 15_000 });
  await page.getByRole('button', { name: '提交交易' }).first().click();
  const dlg = dialogByTitle(page, '提交交易');
  await dlg.waitFor();
  return dlg;
}

/**
 * 产品搜索弹层：搜索 Input 最近的 role=dialog 祖先。
 * Dialog 内打开时（#191 弹层 Portal 注入 DialogContent）排除外层业务 Dialog。
 */
function productPopover(page: Page): Locator {
  return page
    .getByPlaceholder('搜索产品代码/名称')
    .locator('xpath=ancestor::div[@role="dialog"][1]');
}

/**
 * 定位 SearchableProductSelect 触发按钮（aria-haspopup="dialog" + 文本双条件；
 * 同 Dialog 内平台选择框同为 aria-haspopup 按钮，靠 label 文本区分）。
 */
function productTrigger(scope: Page | Locator, label: string): Locator {
  return scope.locator('button[aria-haspopup="dialog"]', { hasText: label }).first();
}

/** 按 data-code + data-market 双属性定位产品选项行（一码多市场分行，单靠 code 不唯一） */
function productOption(popover: Locator, code: string, market: string): Locator {
  return popover.locator(
    `[data-testid="product-option"][data-code="${code}"][data-market="${market}"]`
  );
}

/**
 * 打开产品弹层并搜索 161017，返回弹层 Locator。
 * 关键词防抖 300ms + 服务端搜索，waitFor 覆盖等待；无 LOF 双市场种子时优雅 skip。
 */
async function searchLofOptions(page: Page, dlg: Locator): Promise<Locator> {
  await productTrigger(dlg, '请选择产品').click();
  const popover = productPopover(page);
  await popover.getByPlaceholder('搜索产品代码/名称').fill('161017');
  try {
    await productOption(popover, LOF_SZ.code, LOF_SZ.market).waitFor({ timeout: 10_000 });
  } catch {
    test.skip(true, '环境中没有 161017 LOF 双市场种子数据');
  }
  return popover;
}

test.describe('产品选择器市场标识（防 #259 回归）', () => {
  // ---- 用例 1：LOF 双市场选项分行，市场 Badge 独立可见且文案不同，行 title 完整 ----
  test('搜 161017 出现双市场选项，市场标识独立可见且行 title 完整', async ({ page }) => {
    const errors = collectPageErrors(page);
    const dlg = await openSubmitTradeDialog(page);
    const popover = await searchLofOptions(page, dlg);

    const szOption = productOption(popover, LOF_SZ.code, LOF_SZ.market);
    const otcOption = productOption(popover, LOF_OTC.code, LOF_OTC.market);
    await expect(szOption).toBeVisible();
    await expect(otcOption).toBeVisible();
    // 一码双市场恰分行两条（种子环境确定性数据）
    await expect(popover.getByTestId('product-option')).toHaveCount(2);

    // 三段式契约：名称 / (code) / 市场 Badge 各自独立元素——exact 文本匹配仅当
    // 该文本独占一个元素时命中，长名称截断时 (code) 与市场标识仍是独立可见元素
    await expect(szOption.getByText(LOF_NAME, { exact: true })).toBeVisible();
    await expect(szOption.getByText(`(${LOF_SZ.code})`, { exact: true })).toBeVisible();
    await expect(szOption.getByText(LOF_SZ.marketName, { exact: true })).toBeVisible();
    await expect(otcOption.getByText(`(${LOF_OTC.code})`, { exact: true })).toBeVisible();
    await expect(otcOption.getByText(LOF_OTC.marketName, { exact: true })).toBeVisible();

    // 两行市场标识文案不同（场内/场外可分辨，不出现同一文案或缺失）
    await expect(szOption.getByText(LOF_OTC.marketName, { exact: true })).toHaveCount(0);
    await expect(otcOption.getByText(LOF_SZ.marketName, { exact: true })).toHaveCount(0);

    // 行 title 悬停给出完整「名称 (code) · 市场」（截断部分的全文出口）
    await expect(szOption).toHaveAttribute(
      'title',
      `${LOF_NAME} (${LOF_SZ.code}) · ${LOF_SZ.marketName}`
    );
    await expect(otcOption).toHaveAttribute(
      'title',
      `${LOF_NAME} (${LOF_OTC.code}) · ${LOF_OTC.marketName}`
    );

    expect(errors, `页面抛出未捕获异常: ${errors.join(' | ')}`).toHaveLength(0);
  });

  // ---- 用例 2：选中场外项 → 触发按钮回显「名称 (code) · 市场名」并挂 title 全文本 ----
  test('选中场外项回显含「内地场外」且触发按钮挂完整 title', async ({ page }) => {
    const errors = collectPageErrors(page);
    const dlg = await openSubmitTradeDialog(page);
    const popover = await searchLofOptions(page, dlg);

    await productOption(popover, LOF_OTC.code, LOF_OTC.market).click();

    // 点选后弹层关闭（Radix Popover 关闭即卸载内容）
    await expect(popover.getByPlaceholder('搜索产品代码/名称')).toHaveCount(0);

    // 回显「名称 (code) · 市场名」：DOM 文本为全文（视觉截断不影响断言），
    // 市场后缀使场外项与场内项回显可分辨
    const trigger = productTrigger(dlg, LOF_OTC.marketName);
    await expect(trigger).toBeVisible();
    await expect(trigger).toContainText(`${LOF_NAME} (${LOF_OTC.code})`);
    // 触发按钮挂 title 全文本（名称截断时的悬停全文出口）
    await expect(trigger.locator('[title]')).toHaveAttribute(
      'title',
      `${LOF_NAME} (${LOF_OTC.code}) · ${LOF_OTC.marketName}`
    );

    expect(errors, `页面抛出未捕获异常: ${errors.join(' | ')}`).toHaveLength(0);
  });
});
