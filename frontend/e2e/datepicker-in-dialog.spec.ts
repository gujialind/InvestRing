/**
 * 前端 E2E 测试：弹窗内 DatePicker（防 #191 复发）
 *
 * 背景（issue #191）：modal Dialog 会给 body 置 pointer-events:none（仅 DialogContent
 * 子树恢复 auto），Popover 弹层默认 Portal 到 body 时日历日按钮点击不可达——
 * 点击落在 DialogContent（弹窗保留但日期不写入）或 Overlay（弹窗被整体误关）上。
 * 修复（方案 C）：DialogContent 经 context 暴露 DOM 节点，PopoverContent 在 Dialog 内时
 * 把弹层 Portal 注入 DialogContent。本文件守护该行为不再复发。
 *
 * 数据说明：快照页四个弹窗的「选日写入 + 按钮启用」断言不依赖业务数据，
 * CI 种子库（init_data 的 draft 组合）即可跑；编辑交易用例依赖 pending 交易，
 * 无数据时优雅 skip（与 regression.spec.ts 同一惯例）。
 */
import { test, expect, type Page, type Locator } from '@playwright/test';

/** 日历中「当月 18 号」按钮（data-day=yyyy-MM-18，当月视图内唯一） */
const DAY_18 = 'button.rdp-day_button[data-day$="-18"]';
const DAY_17 = 'button.rdp-day_button[data-day$="-17"]';

/** 进入组合列表，返回首个组合快照页 URL（桌面 /portfolio、移动 /m/portfolio 自适应） */
async function gotoSnapshotsPage(page: Page): Promise<void> {
  await page.goto('/portfolio');
  const firstDetailLink = page.locator('a[href*="/portfolio/"]').first();
  try {
    await firstDetailLink.waitFor({ state: 'visible', timeout: 10_000 });
  } catch {
    test.skip(true, '环境中没有组合数据');
  }
  const href = await firstDetailLink.getAttribute('href');
  await page.goto(`${href}/snapshots`);
  await page.getByRole('button', { name: '追平至日期' }).waitFor({ timeout: 15_000 });
}

/** 进入首个组合的交易页 */
async function gotoTradesPage(page: Page): Promise<void> {
  await page.goto('/portfolio');
  const firstDetailLink = page.locator('a[href*="/portfolio/"]').first();
  try {
    await firstDetailLink.waitFor({ state: 'visible', timeout: 10_000 });
  } catch {
    test.skip(true, '环境中没有组合数据');
  }
  const href = await firstDetailLink.getAttribute('href');
  await page.goto(`${href}/trades`);
  await page.getByRole('button', { name: '提交交易' }).first().waitFor({ timeout: 15_000 });
}

/** 按弹窗标题定位 Dialog（Popover 弹层同样带 role=dialog，需用文案区分） */
function dialogByTitle(page: Page, title: string | RegExp): Locator {
  return page.locator('[role="dialog"]').filter({ hasText: title }).first();
}

/** DatePicker trigger：占位文案或已选日期 */
function pickerTrigger(dlg: Locator, extra?: RegExp): Locator {
  const pat = extra ?? /选择日期|起始日期|结束日期|申请日期|交易日期|除息日|\d{4}-\d{2}-\d{2}/;
  return dlg.locator('button').filter({ hasText: pat }).first();
}

/** 打开日历并点选当日视图中的某日（day 选择器见 DAY_18/DAY_17），断言日历关闭 */
async function pickDay(page: Page, dlg: Locator, daySelector: string, trigger?: Locator): Promise<Locator> {
  const trig = trigger ?? pickerTrigger(dlg);
  await trig.click();
  await page.locator('button.rdp-day_button').first().waitFor();
  await page.locator(daySelector).click();
  await expect(page.locator('button.rdp-day_button')).toHaveCount(0);
  return trig;
}

test.describe('弹窗内 DatePicker（防 #191 复发）', () => {
  // ---- 用例 1：追平至日期 → 选日写入、「开始追平」启用（issue 原断言 1）----
  test('追平快照弹窗：选日写入且「开始追平」启用', async ({ page }) => {
    await gotoSnapshotsPage(page);
    await page.getByRole('button', { name: '追平至日期' }).click();
    const dlg = dialogByTitle(page, '追平快照');
    await dlg.waitFor();

    const trig = await pickDay(page, dlg, DAY_18);
    await expect(dlg).toBeVisible();
    await expect(trig).toHaveText(/20\d{2}-\d{2}-18/);
    await expect(dlg.getByRole('button', { name: '开始追平' })).toBeEnabled();
  });

  // ---- 用例 2：单日生成 → 选日写入、「预检验证」启用（issue 原断言 2）----
  test('单日生成弹窗：选日写入且「预检验证」启用', async ({ page }) => {
    await gotoSnapshotsPage(page);
    await page.getByRole('button', { name: '单日生成' }).click();
    const dlg = dialogByTitle(page, '生成单日快照');
    await dlg.waitFor();

    const trig = await pickDay(page, dlg, DAY_18);
    await expect(dlg).toBeVisible();
    await expect(trig).toHaveText(/20\d{2}-\d{2}-18/);
    await expect(dlg.getByRole('button', { name: '预检验证' })).toBeEnabled();
  });

  // ---- 用例 3：区间重算 → 起止两日期写入、勾选确认后「提交重算任务」启用
  //      （issue 原断言 3 + 症状 2「Dialog 保留但日期不写入」修复实证）----
  test('区间重算弹窗：起止两日期写入、勾选后「提交重算任务」启用', async ({ page }) => {
    await gotoSnapshotsPage(page);
    await page.getByRole('button', { name: '区间重算' }).click();
    const dlg = dialogByTitle(page, '区间重算快照');
    await dlg.waitFor();

    const startTrig = await pickDay(page, dlg, DAY_17, pickerTrigger(dlg, /起始日期/));
    await expect(dlg).toBeVisible();
    await expect(startTrig).toHaveText(/20\d{2}-\d{2}-17/);

    const endTrig = await pickDay(page, dlg, DAY_18, pickerTrigger(dlg, /结束日期/));
    await expect(dlg).toBeVisible();
    await expect(endTrig).toHaveText(/20\d{2}-\d{2}-18/);

    await dlg.getByText('我已了解重算将删除区间内全部快照并重新生成').click();
    await expect(dlg.getByRole('button', { name: '提交重算任务' })).toBeEnabled();
  });

  // ---- 用例 4：批量删除 → 起始日期写入、可触发 dry-run 预览（issue 原断言 4）----
  test('批量删除弹窗：起始日期写入、dry-run 预览可触发', async ({ page }) => {
    await gotoSnapshotsPage(page);
    await page.getByRole('button', { name: '批量删除' }).click();
    const dlg = dialogByTitle(page, '批量删除快照');
    await dlg.waitFor();

    const trig = await pickDay(page, dlg, DAY_17, pickerTrigger(dlg, /选择起始日期/));
    await expect(dlg).toBeVisible();
    await expect(trig).toHaveText(/20\d{2}-\d{2}-17/);

    await dlg.getByRole('button', { name: '预览影响' }).click();
    // dry-run 两种合法终态：有快照列清单 / 无快照提示（CI 种子库无快照）
    await expect(
      dlg.getByText(/将删除 \d+ 张快照|该日期及之后无快照可删除/)
    ).toBeVisible({ timeout: 10_000 });
  });

  // ---- 用例 5：编辑交易弹窗（pending 交易）选日写入（issue 原断言 5）----
  test('编辑交易弹窗：交易日期选日写入', async ({ page }) => {
    await gotoTradesPage(page);
    const editBtn = page.locator('button[title="编辑"]').first();
    try {
      await editBtn.waitFor({ state: 'visible', timeout: 8_000 });
    } catch {
      test.skip(true, '环境中无 pending 交易可编辑');
    }
    await editBtn.click();
    const dlg = dialogByTitle(page, '编辑交易');
    await dlg.waitFor();

    // 交易日期默认预填，改选 18 号
    const trig = await pickDay(page, dlg, DAY_18);
    await expect(dlg).toBeVisible();
    await expect(trig).toHaveText(/20\d{2}-\d{2}-18/);
  });

  // ---- 用例 6：modal={false} 弹窗选日写入不回归（issue 原断言 6；
  //      Task 0.3 实测修正：modal={false} 弹窗选日本来就可用，此处为防回归）----
  test('modal={false} 弹窗：提交交易/申购/事件/现金修正/转移选日写入', async ({ page }) => {
    // 提交交易（TradesContent L575）
    await gotoTradesPage(page);
    await page.getByRole('button', { name: '提交交易' }).first().click();
    let dlg = dialogByTitle(page, '提交交易');
    await dlg.waitFor();
    let trig = await pickDay(page, dlg, DAY_18);
    await expect(dlg).toBeVisible();
    await expect(trig).toHaveText(/20\d{2}-\d{2}-18/);
    await page.keyboard.press('Escape');

    // 申购（SubscriptionsContent L376）
    await page.goto(page.url().replace(/\/trades.*$/, '/subscriptions'));
    await page.getByRole('button', { name: /提交申请|首次申购激活/ }).click();
    dlg = dialogByTitle(page, /提交申请|首次申购激活/);
    await dlg.waitFor();
    trig = await pickDay(page, dlg, DAY_18);
    await expect(dlg).toBeVisible();
    await expect(trig).toHaveText(/20\d{2}-\d{2}-18/);
    await page.keyboard.press('Escape');

    // 份额变动事件（share-change-events L189）：两个 DatePicker，验证除息日
    await page.goto(page.url().replace(/\/subscriptions.*$/, '/share-change-events'));
    await page.getByRole('button', { name: '新建事件' }).click();
    dlg = dialogByTitle(page, '新建份额变动事件');
    await dlg.waitFor();
    trig = await pickDay(page, dlg, DAY_18);
    await expect(dlg).toBeVisible();
    await expect(trig).toHaveText(/20\d{2}-\d{2}-18/);
    await page.keyboard.press('Escape');

    // 持仓页：现金修正 + 平台间现金转移（positions L340/L409）
    await page.goto(page.url().replace(/\/share-change-events.*$/, '/positions'));
    await page.getByRole('button', { name: '更新非净值资产' }).click();
    dlg = dialogByTitle(page, '更新非净值资产');
    await dlg.waitFor();
    trig = await pickDay(page, dlg, DAY_18);
    await expect(dlg).toBeVisible();
    await expect(trig).toHaveText(/20\d{2}-\d{2}-18/);
    await page.keyboard.press('Escape');

    await page.getByRole('button', { name: '现金转移' }).click();
    dlg = dialogByTitle(page, '平台间现金转移');
    await dlg.waitFor();
    trig = await pickDay(page, dlg, DAY_18);
    await expect(dlg).toBeVisible();
    await expect(trig).toHaveText(/20\d{2}-\d{2}-18/);
  });

  // ---- 用例 9：键盘层级——Esc 只关日历不关 Dialog，再 Esc 关 Dialog；
  //      Tab 焦点不逃逸出弹层体系（评审新增）----
  test('键盘层级：Esc 逐层关闭、Tab 焦点不逃逸', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', '移动端无物理键盘语义，仅桌面项目断言');
    await gotoSnapshotsPage(page);
    await page.getByRole('button', { name: '追平至日期' }).click();
    const dlg = dialogByTitle(page, '追平快照');
    await dlg.waitFor();

    await pickerTrigger(dlg).click();
    await page.locator('button.rdp-day_button').first().waitFor();

    // 第一次 Esc：只关日历，Dialog 保留
    await page.keyboard.press('Escape');
    await expect(page.locator('button.rdp-day_button')).toHaveCount(0);
    await expect(dlg).toBeVisible();

    // Tab 焦点应始终在 Dialog（含注入其中的日历弹层）体系内
    await pickerTrigger(dlg).click();
    await page.locator('button.rdp-day_button').first().waitFor();
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press('Tab');
      const inside = await page.evaluate(() => {
        const el = document.activeElement;
        return !!el && el !== document.body && !!el.closest('[role="dialog"]');
      });
      expect(inside, `第 ${i + 1} 次 Tab 后焦点逃逸出弹层体系`).toBe(true);
    }
    await page.keyboard.press('Escape');

    // 第二次 Esc：关 Dialog
    await expect(dlg).toHaveCount(0);
  });

  // ---- 用例 10：弹窗外回归——筛选栏 DatePicker 交互不变（issue 原断言 8，
  //      context 为空时保持 body Portal 默认行为）----
  test('弹窗外 DatePicker（交易页筛选栏）选日写入不回归', async ({ page }) => {
    await gotoTradesPage(page);
    // 筛选栏 DatePicker 占位为「交易日期」
    await page.getByRole('button', { name: '交易日期', exact: true }).first().click();
    await page.locator('button.rdp-day_button').first().waitFor();
    await page.locator(DAY_18).click();
    // 选中后占位文案变为所选日期（弹层关闭、值写入即不回归）
    await expect(page.locator('button.rdp-day_button')).toHaveCount(0);
    await expect(
      page.getByRole('button', { name: /20\d{2}-\d{2}-18/ }).first()
    ).toBeVisible();
  });
});

// ---- 用例 7：移动端 project 跑用例 1–4（/m/portfolio/[code]/snapshots）----
// 移动端与桌面共用 SnapshotsContent（variant=mobile），上述用例在 mobile project
// 会经 middleware 重定向到 /m 路由，天然双端覆盖；本 describe 仅补移动端专属断言。
test.describe('弹窗内 DatePicker 移动端（防 #191 复发）', () => {
  test('移动端快照页四弹窗选日写入', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile', '仅移动端项目');
    await gotoSnapshotsPage(page);
    await expect(page).toHaveURL(/\/m\/portfolio\//);

    for (const [triggerName, title, daySel, extra] of [
      ['追平至日期', '追平快照', DAY_18, undefined],
      ['单日生成', '生成单日快照', DAY_18, undefined],
      ['区间重算', '区间重算快照', DAY_17, /起始日期/],
      ['批量删除', '批量删除快照', DAY_17, /选择起始日期/],
    ] as const) {
      await page.getByRole('button', { name: triggerName }).click();
      const dlg = dialogByTitle(page, title);
      await dlg.waitFor();
      const trig = await pickDay(page, dlg, daySel, extra ? pickerTrigger(dlg, extra) : undefined);
      await expect(dlg).toBeVisible();
      await expect(trig).toHaveText(/20\d{2}-\d{2}-1[78]/);
      await page.getByRole('button', { name: '取消' }).click();
      await expect(dlg).toHaveCount(0);
    }
  });
});

// ---- 用例 8：矮视口可达性（评审新增）：桌面 800×500 / 移动 390×700，
//      四弹窗 + 编辑交易弹窗的执行按钮在视口内可点击 ----
test.describe('弹窗内 DatePicker 矮视口（评审新增）', () => {
  test('矮视口下弹窗执行按钮在视口内可达', async ({ page }, testInfo) => {
    const isMobile = testInfo.project.name === 'mobile';
    await page.setViewportSize(isMobile ? { width: 390, height: 700 } : { width: 800, height: 500 });
    const viewportH = isMobile ? 700 : 500;

    await gotoSnapshotsPage(page);
    const dialogs: Array<[string, string, string]> = [
      ['追平至日期', '追平快照', '开始追平'],
      ['单日生成', '生成单日快照', '预检验证'],
      ['区间重算', '区间重算快照', '提交重算任务'],
      ['批量删除', '批量删除快照', '预览影响'],
    ];
    for (const [triggerName, title, actionName] of dialogs) {
      await page.getByRole('button', { name: triggerName }).click();
      const dlg = dialogByTitle(page, title);
      await dlg.waitFor();
      // 矮视口下日历弹层可用（#161 max-h/overflow 在 Dialog 内不撑破）
      await pickDay(page, dlg, DAY_18);
      // 执行按钮在视口内
      const action = dlg.getByRole('button', { name: actionName });
      await expect(action).toBeVisible();
      const box = await action.boundingBox();
      expect(box, `${title}「${actionName}」无 boundingBox`).not.toBeNull();
      if (box) {
        expect(box.y, `${title}「${actionName}」上缘超出视口`).toBeGreaterThanOrEqual(0);
        expect(box.y + box.height, `${title}「${actionName}」下缘超出 ${viewportH}px 视口`).toBeLessThanOrEqual(viewportH);
      }
      await page.keyboard.press('Escape');
      if (!isMobile) await expect(dlg).toHaveCount(0);
      else await page.waitForTimeout(300);
    }

    // 编辑交易弹窗（字段最多的弹窗）
    await page.goto(page.url().replace(/\/snapshots.*$/, '/trades'));
    const editBtn = page.locator('button[title="编辑"]').first();
    try {
      await editBtn.waitFor({ state: 'visible', timeout: 8_000 });
    } catch {
      test.skip(true, '环境中无 pending 交易可编辑（编辑弹窗矮视口断言跳过）');
    }
    await editBtn.click();
    const dlg = dialogByTitle(page, '编辑交易');
    await dlg.waitFor();
    const save = dlg.getByRole('button', { name: '保存修改' });
    await expect(save).toBeVisible();
    const box = await save.boundingBox();
    expect(box, '编辑交易「保存修改」无 boundingBox').not.toBeNull();
    if (box) {
      expect(box.y + box.height, `编辑交易「保存修改」下缘超出 ${viewportH}px 视口`).toBeLessThanOrEqual(viewportH);
    }
  });
});
