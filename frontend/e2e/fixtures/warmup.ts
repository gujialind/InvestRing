/**
 * E2E 路由预热（warmup project，先于所有浏览器 project 运行）
 *
 * next dev 按需编译路由：某个客户端首次访问未编译路由会触发编译，
 * webpack 随后向所有已连接客户端广播更新；无法 Fast Refresh 的更新
 * 会触发 full reload，取消其他客户端进行中的导航——这正是 PR #169
 * 「webkit 登录后 307 跳转被取消（Load request cancelled）」的根因。
 * 测试前把 E2E 涉及的路由全部请求一遍，让按需编译在测试导航前完成。
 *
 * 受保护路由需带 token cookie 才能真正编译（无 token 会被 middleware
 * 302/307 到登录页，不触发目标路由编译），故先经 API 登录换取 token。
 */
import { test as warmup, expect } from '@playwright/test';

// E2E 各 spec goto 过的公开路由
const PUBLIC_ROUTES = ['/login', '/m/login'];
// E2E 各 spec goto 过的受保护路由（含 middleware 移动重定向目标）
const PROTECTED_ROUTES = [
  '/dashboard',
  '/m/dashboard',
  '/portfolio',
  '/m/products',
  '/settings/tasks',
];

warmup('预编译 E2E 涉及的路由', async ({ request }) => {
  // 冷启动多路由按需编译可能超默认 30s，预留充足余量
  warmup.setTimeout(120_000);
  // 1. 公开路由直接请求（未登录也渲染，触发编译）
  await Promise.all(
    PUBLIC_ROUTES.map((route) =>
      request.get(`http://localhost:3000${route}`).catch(() => {})
    )
  );

  // 2. 经 API 登录拿 token（与 auth.setup.ts 同账号，ADMIN 由 init_data.py 种子）
  const resp = await request.post('http://localhost:3000/api/auth/login', {
    data: { code: 'ADMIN', password: 'admin123' },
  });
  expect(resp.ok()).toBeTruthy();
  const { token } = await resp.json();

  // 3. 带 token cookie 请求受保护路由，触发各路由编译。
  //    /m/* 路由需移动端 UA，否则会被 middleware 重定向回桌面路由
  await Promise.all(
    PROTECTED_ROUTES.map((route) =>
      request
        .get(`http://localhost:3000${route}`, {
          headers: {
            cookie: `token=${token}`,
            ...(route.startsWith('/m')
              ? { 'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile' }
              : {}),
          },
        })
        .catch(() => {})
    )
  );

  // 4. 组合详情子路由（动态段）：从 /portfolio 列表 HTML 提取首个组合 code，
  //    预热 E2E 会 goto 的全部子路由（桌面 + 移动端各一份编译产物）。
  //    不预热时并行测试中首个访问触发按需编译，webpack 广播重建会取消
  //    其他客户端进行中的导航（同 PR #169 根因，#191 spec 曾因此批量失败）
  const listHtml = await (
    await request.get('http://localhost:3000/portfolio', {
      headers: { cookie: `token=${token}` },
    })
  ).text();
  const code = listHtml.match(/\/portfolio\/([A-Za-z0-9_-]+)/)?.[1];
  if (code) {
    const SUB_ROUTES = ['', '/snapshots', '/trades', '/subscriptions', '/share-change-events', '/positions'];
    await Promise.all(
      SUB_ROUTES.flatMap((sub) => {
        const reqs = [
          request
            .get(`http://localhost:3000/portfolio/${code}${sub}`, {
              headers: { cookie: `token=${token}` },
            })
            .catch(() => {}),
        ];
        // 移动端无 share-change-events 子路由（app/m/portfolio/[code]/ 下不存在）
        if (sub !== '/share-change-events') {
          reqs.push(
            request
              .get(`http://localhost:3000/m/portfolio/${code}${sub}`, {
                headers: {
                  cookie: `token=${token}`,
                  'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile',
                },
              })
              .catch(() => {})
          );
        }
        return reqs;
      })
    );
  }
});
