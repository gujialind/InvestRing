/**
 * 前端 E2E 测试：平台选择框搜索（防 #177 回归）
 *
 * 守护 SearchablePlatformSelect 的核心行为契约：
 *   - 客户端按 name/code 过滤（大小写不敏感）、无匹配空态、清空恢复全量；
 *   - 前置特殊项（全部平台/同交易平台）置顶、不参与过滤、点选回传空值语义；
 *   - 点选平台回显 name (code)，筛选请求参数 platform_code 含/不含（评审 R3）；
 *   - 现金转移互斥项可见但禁用（评审 R4）；
 *   - R1：申赎表单原生 <select required> 被替换后，空平台提交须被前端手动校验拦截。
 *
 * 数据说明：搜索词不写死——打开弹层读取第一个平台选项文本，取括号内 code 前 2
 * 字符（转小写，顺带验证大小写不敏感）作为搜索词；无组合/平台/投资人数据时按
 * regression.spec.ts 惯例优雅 skip，不在 CI 造数据。
 */
import { test, expect, type Page, type Locator } from '@playwright/test';

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

/** 进入首个组合的调仓交易页（等待客户端渲染信号：提交交易按钮） */
async function gotoTradesPage(page: Page): Promise<void> {
  const href = await firstPortfolioHref(page);
  await page.goto(`${href}/trades`);
  await page.getByRole('button', { name: '提交交易' }).first().waitFor({ timeout: 15_000 });
}

/** 进入首个组合的申赎页（draft 组合触发按钮文案为「首次申购激活」） */
async function gotoSubscriptionsPage(page: Page): Promise<void> {
  const href = await firstPortfolioHref(page);
  await page.goto(`${href}/subscriptions`);
  await page
    .getByRole('button', { name: /提交申请|首次申购激活/ })
    .first()
    .waitFor({ timeout: 15_000 });
}

/** 进入首个组合的持仓页（桌面端；移动端无「现金转移」入口，调用方需 skip mobile） */
async function gotoPositionsPage(page: Page): Promise<void> {
  const href = await firstPortfolioHref(page);
  await page.goto(`${href}/positions`);
  await page.getByRole('button', { name: '更新非净值资产' }).waitFor({ timeout: 15_000 });
}

/** 按弹窗标题定位业务 Dialog（Popover 弹层同样带 role=dialog，需用文案区分） */
function dialogByTitle(page: Page, title: string | RegExp): Locator {
  return page.locator('[role="dialog"]').filter({ hasText: title }).first();
}

/**
 * 平台搜索弹层：搜索 Input 最近的 role=dialog 祖先。
 * Dialog 内打开时（#191 弹层 Portal 注入 DialogContent）排除外层业务 Dialog。
 */
function platformPopover(page: Page): Locator {
  return page
    .getByPlaceholder('搜索平台名称/代码')
    .locator('xpath=ancestor::div[@role="dialog"][1]');
}

/** 弹层内平台选项文本数组（「名称 (CODE)」整串；特殊项无括号后缀，天然排除） */
async function platformOptionTexts(popover: Locator): Promise<string[]> {
  const texts = await popover.locator('span.min-w-0').allInnerTexts();
  return texts.filter((t) => / \([^()]+\)$/.test(t));
}

/** 选项文本 → code（「名称 (CODE)」取括号段） */
function optionCode(text: string): string {
  const m = text.match(/\(([^()]+)\)$/);
  if (!m) throw new Error(`平台选项文本缺少 (code) 后缀: ${text}`);
  return m[1];
}

/** 读取弹层内第一个平台选项；无平台数据时优雅 skip。keyword = code 前 2 字符小写 */
async function firstPlatformOption(
  popover: Locator
): Promise<{ text: string; code: string; keyword: string }> {
  await popover.locator('span.min-w-0').first().waitFor();
  const texts = await platformOptionTexts(popover);
  test.skip(texts.length > 0, '环境中没有平台数据');
  const text = texts[0];
  const code = optionCode(text);
  return { text, code, keyword: code.slice(0, 2).toLowerCase() };
}

/** 输入搜索词后断言：剩余平台选项均命中 keyword（小写比较）且至少 1 项；返回过滤后文本（轮询等重渲染） */
async function expectFilteredOptions(popover: Locator, keyword: string): Promise<string[]> {
  let texts: string[] = [];
  await expect(async () => {
    texts = await platformOptionTexts(popover);
    expect(texts.length).toBeGreaterThan(0);
    for (const t of texts) {
      expect(t.toLowerCase()).toContain(keyword);
    }
  }).toPass();
  return texts;
}

/** 点选弹层内指定文本的平台选项（getByText 首个匹配为挂 onClick 的行 div，点击冒泡生效） */
async function pickOption(popover: Locator, text: string): Promise<void> {
  await popover.getByText(text, { exact: true }).first().click();
}

test.describe('平台选择框搜索（防 #177 回归）', () => {
  // ---- 用例 1：调仓页筛选平台可搜索 + 特殊项「全部平台」+ 请求参数断言（R3）----
  test('调仓页筛选平台可搜索，保留「全部平台」且请求参数正确', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', '桌面筛选栏断言仅针对桌面项目');
    const errors = collectPageErrors(page);

    // R3「不含」侧：默认（全部平台）进页面，列表请求不带 platform_code。
    // useTradeList staleTime=30s——选平台再切回「全部平台」会命中 fresh 缓存不发请求，
    // 故「不含」断言锚定进页面的初始请求，而非切回后的请求
    const href = await firstPortfolioHref(page);
    const initialResp = page.waitForResponse(
      (r) =>
        r.request().method() === 'GET' &&
        r.url().includes('/api/trades') &&
        !r.url().includes('platform_code='),
      { timeout: 15_000 }
    );
    await page.goto(`${href}/trades`);
    await page.getByRole('button', { name: '提交交易' }).first().waitFor({ timeout: 15_000 });
    await initialResp;

    // 打开筛选栏平台弹层，动态取第一个平台 code 片段作为搜索词
    await page.getByRole('button', { name: '全部平台' }).click();
    const popover = platformPopover(page);
    const { keyword } = await firstPlatformOption(popover);

    // 输入搜索词 → 仅剩命中项；特殊项「全部平台」不参与过滤恒显示
    await popover.getByPlaceholder('搜索平台名称/代码').fill(keyword);
    const matched = await expectFilteredOptions(popover, keyword);
    await expect(popover.getByText('全部平台', { exact: true }).first()).toBeVisible();

    // 点选 → 弹层关闭、触发按钮回显 name (code)；列表请求带 platform_code（R3「含」侧）
    const picked = matched[0];
    const respWith = page.waitForResponse(
      (r) =>
        r.request().method() === 'GET' &&
        r.url().includes('/api/trades') &&
        r.url().includes(`platform_code=${optionCode(picked)}`),
      { timeout: 10_000 }
    );
    await pickOption(popover, picked);
    await respWith;
    const selectedTrigger = page.getByRole('button', { name: picked, exact: true });
    await expect(selectedTrigger).toBeVisible();

    // 重新打开 → 点「全部平台」→ 触发按钮回显恢复
    await selectedTrigger.click();
    const popover2 = platformPopover(page);
    await popover2.getByText('全部平台', { exact: true }).first().click();
    await expect(page.getByRole('button', { name: '全部平台' })).toBeVisible();

    expect(errors, `页面抛出未捕获异常: ${errors.join(' | ')}`).toHaveLength(0);
  });

  // ---- 用例 2：提交交易表单「交易平台」可搜索、「现金平台」默认「同交易平台」置顶 ----
  test('提交交易表单：交易平台可搜索，现金平台默认「同交易平台」', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', '桌面表单断言仅针对桌面项目');
    const errors = collectPageErrors(page);
    await gotoTradesPage(page);
    await page.getByRole('button', { name: '提交交易' }).first().click();
    const dlg = dialogByTitle(page, '提交交易');
    await dlg.waitFor();

    // 交易平台：搜索 → 过滤 → 点选 → 触发按钮回显 name (code)
    await dlg.getByRole('button', { name: '请选择平台' }).click();
    const popover = platformPopover(page);
    const { keyword } = await firstPlatformOption(popover);
    await popover.getByPlaceholder('搜索平台名称/代码').fill(keyword);
    const matched = await expectFilteredOptions(popover, keyword);
    await pickOption(popover, matched[0]);
    await expect(dlg.getByRole('button', { name: matched[0], exact: true })).toBeVisible();

    // 现金平台：未操作时回显特殊项「同交易平台」；打开后特殊项置顶（列表首行）
    const cashTrigger = dlg.getByRole('button', { name: '同交易平台' });
    await expect(cashTrigger).toBeVisible();
    await cashTrigger.click();
    const popover2 = platformPopover(page);
    await expect(popover2.locator('span.min-w-0').first()).toHaveText('同交易平台');

    expect(errors, `页面抛出未捕获异常: ${errors.join(' | ')}`).toHaveLength(0);
  });

  // ---- 用例 3（R1）：申赎表单原生 required 被自定义组件替换后，空平台提交须被前端手动校验拦截 ----
  test('R1：申赎表单未选平台提交被前端拦截', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', '桌面表单断言仅针对桌面项目');
    const errors = collectPageErrors(page);
    await gotoSubscriptionsPage(page);
    await page.getByRole('button', { name: /提交申请|首次申购激活/ }).first().click();
    const dlg = dialogByTitle(page, /提交申请|首次申购激活/);
    await dlg.waitFor();

    // 选投资人（原生 select 保留）、填金额（申购模式默认）；平台刻意不选
    const investorSelect = dlg.locator('select#investor_code');
    const investorCount = await investorSelect.locator('option').count();
    test.skip(investorCount >= 2, '环境中没有投资人数据');
    await investorSelect.selectOption({ index: 1 });
    await dlg.getByLabel('金额（元）').fill('1000');

    // 提交 → 前端拦截：校验 toast 出现、Dialog 保持打开、未发出创建请求
    let createRequested = false;
    page.on('request', (req) => {
      if (req.method() === 'POST' && req.url().includes('/api/subscriptions')) {
        createRequested = true;
      }
    });
    await dlg.getByRole('button', { name: '提交申请' }).click();

    await expect(page.getByRole('heading', { name: '表单校验失败' })).toBeVisible();
    await expect(dlg).toBeVisible();
    expect(createRequested, '未选平台时不应发出创建请求').toBe(false);
    expect(errors, `页面抛出未捕获异常: ${errors.join(' | ')}`).toHaveLength(0);
  });

  // ---- 用例 4：现金转移互斥——对方已选平台在列表中可见但禁用（R4）----
  test('现金转移：对方已选平台可见但禁用，点击不生效', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', '移动端无现金转移功能');
    const errors = collectPageErrors(page);
    await gotoPositionsPage(page);
    await page.getByRole('button', { name: '现金转移' }).click();
    const dlg = dialogByTitle(page, '平台间现金转移');
    await dlg.waitFor();

    // 转出平台选第一项
    await dlg.getByRole('button', { name: '选择转出平台' }).click();
    const popover = platformPopover(page);
    await popover.locator('span.min-w-0').first().waitFor();
    const texts = await platformOptionTexts(popover);
    test.skip(texts.length >= 2, '环境中平台数 < 2，无法验证互斥');
    const picked = texts[0];
    await pickOption(popover, picked);
    await expect(dlg.getByRole('button', { name: picked, exact: true })).toBeVisible();

    // 打开转入平台：已选平台行存在且 aria-disabled；点击不生效（弹层不关闭、值不变）
    await dlg.getByRole('button', { name: '选择转入平台' }).click();
    const popover2 = platformPopover(page);
    const disabledRow = popover2.locator('div[aria-disabled="true"]').filter({ hasText: picked });
    await expect(disabledRow).toHaveCount(1);
    // aria-disabled 元素须 force 点击（绕过 Playwright actionability 的 enabled 等待）
    await disabledRow.click({ force: true });
    await expect(popover2.getByPlaceholder('搜索平台名称/代码')).toBeVisible();
    await expect(dlg.getByRole('button', { name: '选择转入平台' })).toBeVisible();

    expect(errors, `页面抛出未捕获异常: ${errors.join(' | ')}`).toHaveLength(0);
  });

  // ---- 用例 5：移动端平台选择框可搜索（m-positions 弹窗 + trades 移动筛选面板）----
  test('移动端：更新非净值资产与筛选面板的平台选择框可搜索', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile', '仅移动端项目');
    const errors = collectPageErrors(page);
    const href = await firstPortfolioHref(page);

    // /m/portfolio/{code}/positions → 「更新非净值资产」（纯图标触发器）→ 平台搜索点选
    await page.goto(`${href}/positions`);
    await expect(page).toHaveURL(/\/m\/portfolio\//);
    const refreshTrigger = page.locator('button:has(.lucide-refresh-cw)');
    await refreshTrigger.waitFor({ timeout: 15_000 });
    await refreshTrigger.click();
    const dlg = dialogByTitle(page, '更新非净值资产');
    await dlg.waitFor();
    await dlg.getByRole('button', { name: '请选择平台' }).click();
    const popover = platformPopover(page);
    const { keyword } = await firstPlatformOption(popover);
    await popover.getByPlaceholder('搜索平台名称/代码').fill(keyword);
    const matched = await expectFilteredOptions(popover, keyword);
    await pickOption(popover, matched[0]);
    await expect(dlg.getByRole('button', { name: matched[0], exact: true })).toBeVisible();
    await dlg.getByRole('button', { name: '取消' }).click();

    // trades 移动页筛选面板（覆盖 shared 组件 mobile variant）：展开「筛选」→ 平台控件可搜索
    await page.goto(`${href}/trades`);
    await page.getByRole('button', { name: '提交交易' }).first().waitFor({ timeout: 15_000 });
    await page.getByRole('button', { name: '筛选' }).click();
    await page.getByRole('button', { name: '全部平台' }).click();
    const popover2 = platformPopover(page);
    const opt2 = await firstPlatformOption(popover2);
    await popover2.getByPlaceholder('搜索平台名称/代码').fill(opt2.keyword);
    const matched2 = await expectFilteredOptions(popover2, opt2.keyword);
    await pickOption(popover2, matched2[0]);
    await expect(page.getByRole('button', { name: matched2[0], exact: true })).toBeVisible();

    expect(errors, `页面抛出未捕获异常: ${errors.join(' | ')}`).toHaveLength(0);
  });

  // ---- 用例 6：清空搜索词恢复全量 + 无匹配空态 ----
  test('清空搜索词恢复全量，无匹配显示空态提示', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', '桌面筛选栏断言仅针对桌面项目');
    const errors = collectPageErrors(page);
    await gotoTradesPage(page);
    await page.getByRole('button', { name: '全部平台' }).click();
    const popover = platformPopover(page);
    const { keyword } = await firstPlatformOption(popover);

    const rows = popover.locator('span.min-w-0');
    const totalRows = await rows.count(); // 特殊项 1 行 + 全量平台行
    const input = popover.getByPlaceholder('搜索平台名称/代码');

    // 输入搜索词再清空 → 选项恢复全量
    await input.fill(keyword);
    await input.fill('');
    await expect(rows).toHaveCount(totalRows);

    // 不可能命中的词 → 空态提示；平台行清零，特殊项仍置顶
    await input.fill('zzz-none');
    await expect(popover.getByText('无符合条件的平台')).toBeVisible();
    await expect(async () => {
      expect(await platformOptionTexts(popover)).toHaveLength(0);
    }).toPass();
    await expect(rows.first()).toHaveText('全部平台');

    expect(errors, `页面抛出未捕获异常: ${errors.join(' | ')}`).toHaveLength(0);
  });
});
