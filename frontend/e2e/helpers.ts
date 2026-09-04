/**
 * 前端 E2E 共享导航 / 断言 helper（issue #354）。
 *
 * 设计原则：spec 按组合 code 直达，不再经组合列表 `.first()`——list_portfolios
 * 无 ORDER BY，种子新增 E2E_ACTIVE 后「首个组合」不确定（曾使全部业务 spec 命中
 * 漂移）。两个组合是种子契约（backend/tests/seed_base.py），缺组合或形态退化即
 * 硬失败，helper 不做优雅 skip；`test.skip` 只留给真正条件性数据（平台 < 2、
 * 端专属用例、LOF 双市场种子缺失等）。
 *
 * 单一路径：portfolioPath 恒返回桌面路径 /portfolio/{code}[/sub]，mobile project
 * 经 src/proxy.ts 按 UA 重定向到 /m 前缀（Next.js 16 middleware 更名 proxy，#332）
 * ——结构性消除 `href^="/portfolio/"` 类只在桌面成立的定位（regression.spec.ts
 * 旧 mobile bug：移动端锚点 href 为 /m/portfolio/...，`^=` 永不匹配 → 恒 skip）。
 */
import { expect, type Page, type Locator } from '@playwright/test';

/** 种子契约组合（backend/tests/seed_base.py，勿删勿改形态） */
export const E2E_PORT = 'E2E_PORT'; // draft、零交易/申赎/快照
export const E2E_ACTIVE = 'E2E_ACTIVE'; // active、首购 + 已确认场内交易 + 2 日快照 + 1 pending 交易

/** 组合 code 限定为两个种子契约值：typo 即编译期报错，不再退化为运行期 15s 超时（#354 消除静默失败） */
export type PortfolioCode = typeof E2E_PORT | typeof E2E_ACTIVE;

/** 组合子页，与 src/app/portfolio/[code]/ 下路由一一对应 */
export type PortfolioSub =
  | 'trades'
  | 'snapshots'
  | 'subscriptions'
  | 'positions'
  | 'share-change-events';

/** 桌面组合路径；mobile project 靠 middleware 按 UA 重定向到 /m/portfolio/... */
export function portfolioPath(code: PortfolioCode, sub?: PortfolioSub): string {
  return sub ? `/portfolio/${code}/${sub}` : `/portfolio/${code}`;
}

/**
 * 各子页客户端渲染信号：等到其可见再返回，避免首帧空判（列表/表单为客户端 fetch）。
 * positions 信号「更新非净值资产」为桌面专属——移动端 positions 是独立实现
 * （m/positions/page.tsx，触发器为纯图标 cash-update-trigger），移动端调用方须用
 * portfolioPath 自行 goto 并等 cash-update-trigger（见 platform-select-search
 * 「移动端：更新非净值资产与筛选面板的平台选择框可搜索」用例）。
 */
const SUBPAGE_READY: Record<PortfolioSub, (page: Page) => Locator> = {
  trades: (page) => page.getByRole('button', { name: '提交交易' }).first(),
  snapshots: (page) => page.getByRole('button', { name: '追平至日期' }),
  subscriptions: (page) => page.getByRole('button', { name: /提交申请|首次申购激活/ }).first(),
  positions: (page) => page.getByRole('button', { name: '更新非净值资产' }),
  'share-change-events': (page) => page.getByRole('button', { name: '新建事件' }),
};

/** 进入组合详情页，等待页头 h1（组合名，draft/active 与双端均渲染）可见 */
export async function gotoPortfolioDetail(page: Page, code: PortfolioCode): Promise<void> {
  await page.goto(portfolioPath(code));
  await page
    .getByRole('heading', { level: 1 })
    .first()
    .waitFor({ state: 'visible', timeout: 15_000 });
}

/** 进入组合子页并等待该页渲染信号（positions 信号桌面专属，见 SUBPAGE_READY 注） */
export async function gotoPortfolioSubpage(
  page: Page,
  code: PortfolioCode,
  sub: PortfolioSub,
): Promise<void> {
  await page.goto(portfolioPath(code, sub));
  await SUBPAGE_READY[sub](page).waitFor({ state: 'visible', timeout: 15_000 });
}

/** 按弹窗标题定位业务 Dialog（Popover 弹层同样带 role=dialog，需用文案区分） */
export function dialogByTitle(page: Page, title: string | RegExp): Locator {
  return page.locator('[role="dialog"]').filter({ hasText: title }).first();
}

/**
 * 收集页面未捕获异常（客户端崩溃防线），用例末尾断言为空。
 * 豁免 Next.js standalone/mobile 的 RSC `_rsc` prefetch 被重定向层拦下的框架级
 * `access control` 噪音（`/m/...?_rsc=... due to access control checks`）：移动端
 * 导航至组合页时必然出现，页面功能与渲染均正常，非产品 bug；其余错误照常严格断言。
 */
export function collectPageErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('pageerror', (e) => {
    const msg = e.message;
    if (/access control checks/.test(msg) && /_rsc=/.test(msg)) return;
    errors.push(msg);
  });
  return errors;
}

/**
 * 后端仅认 Authorization: Bearer 头（token 存 localStorage，无 cookie 回退），
 * page.request 不会自动附带，须从页面 localStorage 显式读取后传递。
 */
export async function authHeaders(page: Page): Promise<{ Authorization: string }> {
  const token = await page.evaluate(() => window.localStorage.getItem('token'));
  expect(token, '页面 localStorage 中缺少登录 token，无法调用后端 API').toBeTruthy();
  return { Authorization: `Bearer ${token}` };
}
