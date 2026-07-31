# InvestRing 前端全面排查报告

排查日期：2026-07-30
排查范围：`frontend/src/**`（122 个 TS/TSX 文件，约 12300 行）+ 工程配置
契约基线：`backend/openapi.json`（101 个端点）、`backend/app/routers/`、`backend/app/schemas/`
实测环境：http://<server-ip>（PC 浏览器实测 + 移动 UA curl 验证），账号 ADMIN

## 排查方法与覆盖度

| 方向 | 手段 | 状态 |
|------|------|------|
| 架构设计与代码坏味道 | 逐文件静态审查 + 全仓 grep 引用分析 | 完成 |
| 前后端契约一致性 | 前端 16 个 api 模块 / 15 个类型文件 逐一对照后端路由与 schema | 完成 |
| 页面交互与布局 | 浏览器实测 15 个 PC 页面 + 3 组业务流写操作 | 完成 |
| 移动端 | 移动 UA HTTP 验证 + 代码审查（真机 UA 浏览器不可得，见下） | 部分完成 |
| 工程质量门禁 | lint / tsc / build | 完成（2026-07-30 补跑，Node 24，见下） |

### 两项执行限制（如实说明）

1. **lint / tsc / build 已于报告发布当日补跑通过**（初版报告时 WSL 内 Node 环境不可用）。环境：WSL 内 nvm 安装的 Node v24.18.1 / npm 11.16.0，`npm install` 后执行：
   - `npm run lint`：**0 error / 21 warning**，全部为 `@typescript-eslint/no-unused-vars`（未使用的 import 与变量，散布于 share-change-events、settings、Navbar、BottomNav、PortfolioListContent、ClosePortfolioDialog、dropdown-menu、select 等文件），与 P2-3/P2-5 的死代码结论互相印证。
   - `npx tsc --noEmit`：**0 error**。注意：tsc 通过不代表本报告的契约问题不存在——P0-2（tasks 分页）、P1-19/20（类型字段错位）属于「前端类型自洽但与后端实际返回不符」，编译器无法发现，仍以人工比对与运行时实测为准。
   - `npm run build`：**通过**（Next.js 15，28 个路由全部构建成功，Node 24 运行时下验证）。
2. **移动端未能用真机 UA 在浏览器中走查**：可用的浏览器工具 UA 为桌面 Electron，`middleware.ts` 会把 `/m/*` 重定向回 PC 路径。改用移动 UA 发起 HTTP 请求验证了路由与 SSR 输出（下文 P0-1 即由此确认），其余移动端问题基于代码审查，已标注“未实测”。

## 问题统计

| 等级 | 数量 | 含义 |
|------|:---:|------|
| P0 | 8 | 功能不可用、页面崩溃、用户可直接触达的错误 |
| P1 | 20 | 数据错误、交互缺陷、契约不一致导致的隐性失效 |
| P2 | 16 | 坏味道、死代码、一致性与工程治理 |

## 修复进度（2026-07-30，第一批 + 第二批已实施）

- **P0 全部 8 项已修复**：P0-1（/m/login 豁免 + 水合，含 P1-18）、P0-2/P0-6（task api 对齐分页，后端新增 `GET /system/tasks/executions` 全局执行历史端点）、P0-3（改密 PUT）、P0-4（useUpdateInvestor 传参重构）、P0-5（移除删除组合入口，对齐后端 RESTRICT 设计）、P0-7（删除日志导航死链，废弃 logApi.taskLogs）、P0-8（6 页抽为 shared Content + 移动端真薄壳，MobileLayout 只在 m/layout 出现一次）。
- **已修复的 P1**：P1-4（配色统一 getReturnColorClass）、P1-5（akshare 独立 PUT + 开关回填 + 空 token 不覆盖）、P1-7（401 统一 authStore.logout）、P1-11（ApiException 保留 details；DUPLICATE_TRADE 确认重试、MARKET_AMBIGUOUS 展示可选市场、PLATFORM_NOT_COVERED 引导 force_cover）、P1-13（字符串 detail 分支）、P1-14（SubscriptionsContent 改用统一 hook）、P1-17（三处 invalidate 错 key 随内联 mutation 消灭而根治）、P1-18（移动端水合等待）、P1-19 部分（TradeUpdate/SubscriptionUpdate 字段对齐，TradeCreate 补 allow_duplicate）、P1-20 部分（types/log.ts 字段全量对齐后端）。
- **已顺带修复的 P2**：P2-1/P2-6 部分（新增 useTask/useShareChangeEvent/useSystem hooks + queryKeys 工厂，页面内联 mutation 已清零）、P2-2 部分（现金重估 mutation 双端共用 useUpdateCashPosition）、P2-7（lib/queryKeys.ts）、“Next.js 14”文案。
- **验证**：`tsc --noEmit` 0 error、`eslint` 0 error/21 warning（均为存量死代码 no-unused-vars）、`next build` 通过；后端 `pytest` 390 个全部通过。
- **部署后回归**（dev 已上线）：移动 UA `/m/login` 正常渲染登录表单、`/api/system/tasks/executions` 200、改密 400+中文错误（不再 405/英文）、任务页无崩溃且执行历史自动刷新、编辑投资人 200、删除组合与日志入口已消失。

## 修复进度（第三批已实施）

功能闭环与契约对齐：

- **P1-1 持仓盈亏三列**：后端 `GET /api/positions` 补读侧派生字段 `product_name`（批量取 product 表）、`profit_loss`、`profit_loss_percent`（仅净值型；现金行为 None），`PositionResponse` 同步补 `asset_type`。
- **P1-2 净值曲线**：新增 `portfolioApi.getNavHistory` + `useNavHistory`，PC 与移动端详情页改用历史序列（不再只传最新快照单点）。
- **P1-3 收益率**：新增 `getReturns` + `usePortfolioReturns`，tab 改为累计/年化两项并展示后端真实值（移除后端不提供的 TWR 假选项，年化附持有天数）。
- **P1-15 现金转移闭环**：新增 `CashTransferListDialog`（持仓页“转移记录”入口），展示分组记录并为在途（两腿 pending）转移提供“确认到账”——跨天转移不再永久卡在 pending。
- **P1-16 通知入口**：新增 `useNotification` + `NotificationBell`（Navbar 铃铛、未读角标、单条/全部已读、60s 轮询）；types/notification.ts 字段全量对齐后端。
- **P1-8 角色守卫**：新增 `AdminGuard`，包裹 investors/platforms/products/settings-tasks 的 PC 与移动端共 8 个页面（viewer 直接输 URL 得到友好提示而非空表格 + 一串 403）。
- **P1-9 登出**：`useLogout` 补调 `POST /api/auth/logout`（token 黑名单 + 登出日志，失败不阻断本地）；Navbar 改用该 hook，同时清 react-query 缓存。
- **P1-19/20 类型与路径**：`ShareChangeEvent*` 补 `entitlement_shares`/`cash_product_code`/`event_source`/`parent_event_id`/`tushare_event_id` 并移除 Update 中的 `status`；`snapshot.ts` 补 `warnings` 与 `negative_cash_platforms`（快照页已接入负现金预警 Alert）；`ProductCreate` 补 `data_source`/`sync_history`；`TradingCalendarDay` 移除后端不返回的 `week_day`/`notes`；`productApi` 的 market 改为必填校验（`requireMarket` 抛 `MARKET_REQUIRED`，不再发出 `/products/CODE/` 畸形 URL），`get` 改走路径参数而非无效 query。
- **验证**：`tsc` 0 error、`eslint` 0 error/19 warning（较上一批减 2）、`next build` 通过；后端 `pytest` **420 个全部通过**。

第四批（工程治理）已实施：

- **P2-3/4/5 死代码与未用依赖**：删除 9 个零引用组件（desktop/Sidebar、DataTable、SplitPane、mobile/ActionSheet、CardStack、charts/AllocationPie、ReturnChart、shared/TradeForm、StatCard，约 780 行）；`sonner` 依赖从 package.json 与 lockfile 彻底移除（实际用自研 ToastContainer）。
- **lint warning 清零**：从 21 降至 **0 warning / 0 error**（清理未使用 import 与变量）。其中 snapshots 页的 `handleDelete` 未被调用是真实功能缺口，已补上“删除最新快照”入口（遵循快照连续原则，仅允许从最新日往前删）。
- **P2-9/10 精度口径**：新增语义化函数 `formatShares`（2 位）、`formatNav`（4 位、不带 ¥）、`formatAmount4`；持仓页净值/成本价列、交易与申赎价格列、产品价格历史、dashboard 份额展示全部改用新函数（不再用 `formatCurrency` 展示净值或裸 `toLocaleString`）；份额事件的 `shares_change` 输入 step 由 0.0001 改为 0.01（对齐后端 2 位，避免静默量化）。
- **P2-8 部分**：`deepClone` 改用 `structuredClone`（原 JSON 往返丢 Date/undefined）。**utils.ts 未做物理拆分** —— 拆分会牍动 100+ 处 import、收益纯机械，风险大于价值，保留分区注释以待后续需要时再拆。
- **P2-11 原生 confirm 清零**：新增通用 `ConfirmDialog`，替换7 处原生 `confirm()`（任务执行、删除平台/产品/投资人/快照），全仓已无 `confirm()` 调用。
- **P2-13**：`BottomNav` 路径加 `/m` 前缀（修正移动端高亮失效 + 每次点击多一次 307 重定向）；`app/page.tsx` 改为纯占位（去除与 middleware 重复的客户端跳转）；`key={idx}` 改为稳定 key。
- **第二批漏项补完**：`PlatformsContent` 仍为内联 mutation，已补 `useCreatePlatform`/`useUpdatePlatform`/`useDeletePlatform` 并切换（现全仓页面/组件内联 mutation 彻底清零）。
- **P2-14 CI 前端门禁**：`ci.yml` 新增 `frontend-check` job（Node 24 + `npm ci` + `eslint` + `tsc --noEmit` + `next build`），文件头注释同步更新。
- **P2-16 E2E**：新增 `e2e/regression.spec.ts`（5 个用例，逐个标注所防 P0：任务页崩溃、日志死链、删除组合入口、`/m/login` 空白、移动端 PC 侧栏）。**顺带修了一个真 bug**：现有 `auth.spec.ts` 与 `auth.setup.ts` 用 `getByLabel('用户编码')`，而登录页实际 label 是“用户名”——原有 E2E 用例本身是坏的，一直无法通过。
- **验证**：`eslint` **0 error / 0 warning**、`tsc` 0 error、`next build` 通过；后端 `pytest` 420 个全部通过；CI 现含 4 个 job（backend-test / backend-test-mysql / cli-contract-check / frontend-check）。

尚未处理（需单独评估）：P1-6（dashboard 客户端聚合，需后端新增聚合端点）、P1-10（后端 viewer 可越权读 trades/positions，属后端权限设计）、P1-21（窄视口表格溢出，需移动端表格改卡片布局）、utils.ts 物理拆分、`Dialog modal={false}`（7 处，改动需逐个验证弹窗补捕行为）。

---

# P0 —— 功能不可用 / 崩溃

## P0-1 移动端完全无法登录（`/m/login` 渲染为空白）

[app/m/layout.tsx](file:///home/collyn/projects/InvestRing/frontend/src/app/m/layout.tsx#L16-L24) 对 `/m/**` 下所有页面施加鉴权守卫，而 `/m/login` 本身也在该 layout 之下：

```tsx
useEffect(() => { if (!isAuthenticated) router.push("/m/login"); }, [isAuthenticated, router]);
if (!isAuthenticated) return null;      // ← /m/login 自己也被这行吞掉
```

未登录时 `isAuthenticated === false`（[authStore.ts#L34](file:///home/collyn/projects/InvestRing/frontend/src/stores/authStore.ts#L34) 初值），layout 返回 `null`，登录表单永远不渲染，同时 `useEffect` 反复 push 同一路径。

实测证据（移动 UA curl）：

```
GET /               → 307 → /m/dashboard
GET /m/dashboard    → 307 → /m/login          （middleware 无 token 重定向）
GET /m/login        → 200，8631 字节，正文中无“用户名/密码/登录”，连 <main> 都不存在
对照 GET /login     → 200，正文含“用户名”×2、“密码”×2、“登录”×1
```

影响：真实手机访问站点 → middleware 送到 `/m/login` → 白屏，移动端整体不可用。
修复：把 `/m/login` 移出鉴权守卫（在 layout 中判断 `pathname === "/m/login"` 时直接 `return children`，或将登录页移到 route group 之外）。同时补上 PC 侧已有的水合等待逻辑（见 P1-18）。

## P0-2 `/settings/tasks` 白屏崩溃

后端 [tasks.py#L20](file:///home/collyn/projects/InvestRing/backend/app/routers/tasks.py#L20) `@router.get("")` 返回分页对象 `{items, total, page, page_size}`，前端 [api/task.ts#L5-L6](file:///home/collyn/projects/InvestRing/frontend/src/lib/api/task.ts#L5-L6) 声明为 `ScheduledTask[]`，页面 [settings/tasks/page.tsx#L31](file:///home/collyn/projects/InvestRing/frontend/src/app/settings/tasks/page.tsx#L31) 写：

```ts
const tasks: ScheduledTask[] = tasksData || [];   // 实际拿到对象，truthy
```

随后 `tasks.map(...)` 抛错。实测：页面显示 `Application error: a client-side exception has occurred`，console 报 `g.map is not a function`，刷新后依旧崩溃，无恢复入口。截图 `/tmp/test6_tasks_crash.png`。
对照：`api/log.ts` 有 `unwrap()` 兼容处理，task 模块漏了。
修复：`taskApi.list` 返回类型改为分页并解包。

## P0-3 修改密码必然失败（405）

前端 [api/auth.ts#L13-L14](file:///home/collyn/projects/InvestRing/frontend/src/lib/api/auth.ts#L13-L14) 用 `POST /auth/password`，后端 [auth.py#L122](file:///home/collyn/projects/InvestRing/backend/app/routers/auth.py#L122) 是 `@router.put("/password")`。
实测：`POST /api/auth/password → 405`，页面提示“密码修改失败 / Request failed with status code 405”（英文 axios 原文，见 P1-13）。截图 `/tmp/test1_password_405.png`。
修复：改为 `PUT`（一行）。

## P0-4 编辑投资人必然失败（code 传空串）

[app/investors/page.tsx#L33](file:///home/collyn/projects/InvestRing/frontend/src/app/investors/page.tsx#L33)：

```ts
const updateInvestor = useUpdateInvestor("");
```

[useInvestor.ts#L55-L60](file:///home/collyn/projects/InvestRing/frontend/src/hooks/useInvestor.ts#L55-L60) 的 code 是闭包参数，恒为空串 → 请求打到 `/api/investors/`。
实测：创建 TEST_QA1 后编辑改名 → `PUT /api/investors/ → 307` → `PUT /api/investors → 405`，名称未更新。截图 `/tmp/test2_investor_edit_failed.png`（测试数据已清理）。
修复：改为 `mutationFn: ({code, data}) => investorApi.update(code, data)`。

## P0-5 删除组合功能整体不存在（405）

前端 [api/portfolio.ts#L30-L31](file:///home/collyn/projects/InvestRing/frontend/src/lib/api/portfolio.ts#L30-L31) 有 `DELETE /portfolios/{code}`，`useDeletePortfolio` 被 3 处 UI 使用（`portfolio/[code]/page.tsx:42`、`m/portfolio/[code]/page.tsx:30`、`PortfolioListContent.tsx:69`）。后端 [portfolios.py](file:///home/collyn/projects/InvestRing/backend/app/routers/portfolios.py) 全部路由为 get/post/put，**无 DELETE**。
实测：删除 TESTQA01 → `DELETE /api/portfolios/TESTQA01 → 405`，提示“删除失败 / Request failed with status code 405”。截图 `/tmp/test3_portfolio_delete_405.png`。
注：这与 AGENTS.md “所有实体删除均为 RESTRICT，通过关闭/停用管理生命周期”的设计一致 —— 即**后端故意不提供删除**，前端不应有此按钮。
修复：删除前端删除入口与 api 方法，改为引导用户使用“关闭组合”。
遗留：测试组合 `TESTQA01` 因此无法删除，仍存于环境中。

## P0-6 任务执行历史恒 404

前端 [api/task.ts#L17-L18](file:///home/collyn/projects/InvestRing/frontend/src/lib/api/task.ts#L17-L18) `GET /system/tasks/executions`，后端无此路由，会被 [tasks.py#L161](file:///home/collyn/projects/InvestRing/backend/app/routers/tasks.py#L161) `GET /system/tasks/{code}` 以 `code="executions"` 捕获 → 404 “Task not found”。实测 network 确认。
正确端点是 `GET /system/tasks/{code}/logs`（按任务维度）；若需全局历史需后端新增。
同类：[api/log.ts#L32-L33](file:///home/collyn/projects/InvestRing/frontend/src/lib/api/log.ts#L32-L33) `GET /system/logs/task` 也不存在（logs 路由只有 login/audit/error），该方法目前无调用方。

## P0-7 侧边栏“日志”菜单指向不存在的页面（404）

[components/layout/Sidebar.tsx#L24](file:///home/collyn/projects/InvestRing/frontend/src/components/layout/Sidebar.tsx#L24) 有 `{ href: "/settings/logs", label: "日志" }`，但 `app/settings/logs/page.tsx` 不存在。实测点击后 404。截图 `/tmp/15_settings_logs_404.png`。
AGENTS.md §5.5 声称存在 `/settings/logs` 与 `/m/settings/logs` 两个页面，**均为文档虚构**；配套的 `logApi` 三个方法（login/audit/error）也无任何页面消费 —— 日志功能只做了 API 层。
修复：二选一 —— 补实现日志页面，或移除导航项并删除死 api。

## P0-8 6 个移动端页面直接复用 PC 页面组件，导致双层布局

以下 `/m` 页面全部形如 `import XxxPage from "@/app/xxx/page"; return <XxxPage />;`：

```
app/m/login/page.tsx          app/m/investors/page.tsx     app/m/products/page.tsx
app/m/platforms/page.tsx      app/m/settings/page.tsx      app/m/settings/tasks/page.tsx
```

PC 页面内部渲染 `MainLayout`（Navbar + Sidebar + PC 内边距），而 `app/m/layout.tsx` 外层已包 `MobileLayout`（BottomNav + `pb-16` + `p-4`）→ 移动端出现 PC 顶栏/侧栏 + 底部 Tab 双导航、双层内边距。
对照正确形态：`app/m/portfolio/[code]/trades/page.tsx` 等为 6 行薄壳 → `<MobileLayout><TradesContent variant="mobile" basePath="/m/portfolio"/></MobileLayout>`。
另有 `MobileLayout` 重复嵌套：`m/layout.tsx` 已包一层，`m/dashboard`、`m/portfolio/[code]` 等页面内又自包一层。
未实测（受 UA 限制），但代码路径确定。`/m/settings/tasks` 还会连带继承 P0-2 的崩溃。
修复：把这些 PC 页面内容抽为不含布局的 `components/shared/*Content.tsx`，PC 页与移动薄壳页各自套自己的布局；`MobileLayout` 只在 `m/layout.tsx` 出现一次。

---

# P1 —— 数据错误 / 交互缺陷 / 契约不一致

## 数据展示错误

**P1-1 持仓表“产品名称 / 盈亏 / 收益率”三列永久为空。** [types/position.ts](file:///home/collyn/projects/InvestRing/frontend/src/types/position.ts) 定义了 `product_name`、`profit_loss`、`profit_loss_percent`，后端 `PositionResponse` 与 `portfolio_position` 模型均无这三个字段。[positions/page.tsx#L595,L610-L621](file:///home/collyn/projects/InvestRing/frontend/src/app/portfolio/[code]/positions/page.tsx#L595) 渲染了这三列。实测：产品行三列显示 `-`。同时前端类型缺后端确实返回的 `asset_type`。
修复：后端补算这三个派生字段，或前端删列（推荐前者，盈亏是核心信息）。

**P1-2 净值走势图只有一个数据点。** [portfolio/[code]/page.tsx#L338-L344](file:///home/collyn/projects/InvestRing/frontend/src/app/portfolio/[code]/page.tsx#L338-L344) 传给 `NavCurve` 的 data 是 `[{date: snapshot.snapshot_date, nav: snapshot.unit_price}]` —— 仅最新快照单点。后端有 `GET /api/portfolios/{code}/nav-history`（支持 start/end）但前端 api 层未封装。移动端 `m/portfolio/[code]/page.tsx#L146` 同样。实测：图上只有 “07-01 初始净值” 一个点。截图 `/tmp/11_portfolio_nav_history.png`。

**P1-3 收益率 tab 是纯 UI 假象。** [portfolio/[code]/page.tsx#L161-L192](file:///home/collyn/projects/InvestRing/frontend/src/app/portfolio/[code]/page.tsx#L161-L192) 有 累计/年化/TWR 三个切换，后端 `GET /api/portfolios/{code}/returns` 未被调用。实测：切换只改说明文案，不发任何请求，数值恒为列表接口的 `cumulative_return`。

**P1-4 涨跌配色双端相反。** [lib/utils.ts#L197-L198](file:///home/collyn/projects/InvestRing/frontend/src/lib/utils.ts#L197-L198) `getReturnColorClass` 按中国惯例红涨绿跌；而 PC 持仓页 [positions/page.tsx#L569,L611,L620](file:///home/collyn/projects/InvestRing/frontend/src/app/portfolio/[code]/positions/page.tsx#L611) 硬编码 `>= 0 ? "text-green-600" : "text-red-600"`（绿涨红跌）。移动端持仓页用的是 utils 版本 → 同一数据两端颜色语义相反。这是复制粘贴导致的漂移实例（见 P2-2）。

**P1-5 数据源配置：AkShare 开关永不生效 + 表单覆盖风险。** [settings/page.tsx#L110-L133](file:///home/collyn/projects/InvestRing/frontend/src/app/settings/page.tsx#L125) 硬编码 `source: "tushare"`，把 `akshare_enabled` 塞进同一请求的 `is_enabled`，而后端 [data_sources.py#L93-L103](file:///home/collyn/projects/InvestRing/backend/app/routers/data_sources.py#L93-L103) 的 tushare 分支只处理 `api_key`、忽略 `is_enabled`；从不请求 `PUT /system/data-sources/akshare`。另 L29-32 本地 state 初始为空、服务端值只作 placeholder，只改一项保存会把其余字段以空值提交。

**P1-6 dashboard 统计在数据量 >100 时静默出错。** [useDashboardStats.ts#L29-L32](file:///home/collyn/projects/InvestRing/frontend/src/hooks/useDashboardStats.ts#L29-L32) 拉 4 个列表各 `page_size=100` 在前端 reduce 求和/均值，超量无提示。后端缺 dashboard 聚合端点。

## 认证与权限

**P1-7 401 时认证状态三方不一致。** token 写三份（[authStore.ts#L37-L43](file:///home/collyn/projects/InvestRing/frontend/src/stores/authStore.ts#L37-L43)：localStorage + cookie + zustand persist），而消费方各看一处：middleware 看 cookie、axios interceptor 看 localStorage、组件看 zustand。[client.ts#L47-L50](file:///home/collyn/projects/InvestRing/frontend/src/lib/api/client.ts#L47-L50) 401 时**只清 localStorage**，cookie 与 zustand 仍在 → 出现“页面认为已登录、所有请求 401”的僵死态。
修复：401 分支改调 `useAuthStore.getState().logout()`（内部已清三处）。

**P1-8 admin 专属页面无角色守卫。** `useRoleCheck().isAdmin` 仅用于 3 处（组合详情 PC/移动、PortfolioListContent）。`investors`、`products`、`platforms`、`settings`、`settings/tasks` 五个管理页无任何角色检查，middleware 也只校验 token 存在性。viewer 直接输 URL 即可进入并看到操作按钮（后端权限是硬的，无数据泄露，属体验问题）。

**P1-9 登出不清 react-query 缓存、不通知后端。** [Navbar.tsx#L19-L22](file:///home/collyn/projects/InvestRing/frontend/src/components/layout/Navbar.tsx#L20) 内联重写登出，未 `queryClient.clear()` → 换账号登录可能看到上个账号的缓存数据；同时后端 `POST /api/auth/logout` 从不调用（登录日志缺 logout 记录）。实测确认无 logout 请求。已有的 `useLogout` hook 无人使用。

**P1-10 后端侧越权读取（顺带发现）。** `GET /api/trades`、`GET /api/positions` 用 `get_current_user` 且无投资人维度过滤，viewer 可读全部组合的交易与持仓；`GET /api/system/data-sources` 亦为普通用户可读（返回脱敏 key）。属后端问题，一并记录。

## 错误处理与业务流闭环

**P1-11 `detail.details` 被丢弃，两个业务流程无法恢复。** 后端 [main.py#L55-L60](file:///home/collyn/projects/InvestRing/backend/app/main.py#L55-L60) 会附带 `detail.details`，前端 `ApiErrorDetail`/`ApiException`（[client.ts#L57-L82](file:///home/collyn/projects/InvestRing/frontend/src/lib/api/client.ts#L57-L82)）只保留 `{code, message, status}`。直接后果：
- `MARKET_AMBIGUOUS` 的 `details.available_markets` 拿不到 → LOF 一码多市场产品无法在前端选市场，交易流程卡死。
- `DUPLICATE_TRADE` 需要 `allow_duplicate=true` 重试，而 [types/trade.ts#L22-L35](file:///home/collyn/projects/InvestRing/frontend/src/types/trade.ts#L22-L35) 的 `TradeCreate` 缺该字段（后端有），类型层面就无法重试。
- 份额事件平台覆盖不全需要 `force_cover`，[api/share-change-event.ts#L20-L21](file:///home/collyn/projects/InvestRing/frontend/src/lib/api/share-change-event.ts#L20-L21) 未支持该 query。

**P1-12 15 个关键业务错误码中 14 个无专门 UI 处理。** 唯一有专门处理的是 `SNAPSHOT_DEPENDENCY`（[useTrade.ts#L367-L375](file:///home/collyn/projects/InvestRing/frontend/src/hooks/useTrade.ts#L367-L374)，且仅覆盖申购 unconfirm，trade unconfirm 未覆盖）。其余（`INSUFFICIENT_CASH`/`INSUFFICIENT_SHARES`/`NON_TRADING_DAY`/`DATE_BEFORE_SNAPSHOT`/`SNAPSHOT_NOT_CONTINUOUS`/`CASH_TRADE_FORBIDDEN`/`PRICE_NAV_MISMATCH`/`CANNOT_CANCEL_EXCHANGE`/`CANNOT_MODIFY_CONFIRMED`/`PENDING_TRANSACTIONS_EXIST`/`INVESTOR_HAS_SHARES`/`TRANSFER_NOT_READY`）全部降级为通用 toast。
实测校验：`NON_TRADING_DAY` 显示“非交易日，请等待交易日再提交”、`DATE_BEFORE_SNAPSHOT` 显示“申请日必须晚于最新快照日（2026-07-01）”—— **后端 message 质量高，通用 toast 对这两类够用**。真正需要交互恢复的只有 P1-11 的三个，其余可只做前置校验（如日期选择器接 `trading-calendar/is-open`，该端点前端未用）。

**P1-13 后端字符串 `detail` 导致用户看到英文 axios 原文。** 后端有 30+ 处 `HTTPException(detail="Trade not found")` 这类字符串 detail（trades/subscriptions/positions/products/portfolios/tasks/notifications 等），此时 `detail?.error` 与 `detail?.message` 均为 undefined，前端回落到 `axiosError.message`。实测 P0-3 即显示 “Request failed with status code 405”。
修复：前端 `handleApiError` 增加 `typeof detail === "string"` 分支；后端逐步统一改用 `BusinessError`/`NotFoundError`。

**P1-14 `SubscriptionsContent` 的错误解析恒失效。** [SubscriptionsContent.tsx#L140-L144](file:///home/collyn/projects/InvestRing/frontend/src/components/shared/SubscriptionsContent.tsx#L141-L142) 手写 `error.response?.data?.detail?.message`，但 `request()` 抛出的是 `ApiException`（无 `response` 属性）→ 恒 fallback 到“删除失败”，真实原因被吞。

**P1-15 跨天现金转移创建后无法确认。** `cash-transfer` 三个端点中只有 `create` 有入口（持仓页对话框），`confirm` 与 `list` 的 hook 存在但无任何 UI 调用 → `cross_day=true` 的转移两腿永久 pending，资金在途无法落地，配合 `TRANSFER_NOT_READY` 无处理，用户无从知晓。

**P1-16 通知功能零入口。** `notificationApi`（3 端点、路径方法均正确）从 `lib/api/index.ts` 导出，但全仓零引用：无铃铛、无未读角标、无列表。后端通知模型与定时任务产出的通知用户完全看不到。

**P1-17 mutation invalidate key 不匹配，列表不刷新（3 处）。** 根因都是页面内联 mutation 不知道 hooks 的 key 结构：
- [positions/page.tsx#L100](file:///home/collyn/projects/InvestRing/frontend/src/app/portfolio/[code]/positions/page.tsx#L100) `["trades", code]` ≠ hooks 的 `["trades","list",params]`，且漏 invalidate `["positions", code]` → 建交易后两个列表都不刷新。
- [SubscriptionsContent.tsx#L138](file:///home/collyn/projects/InvestRing/frontend/src/components/shared/SubscriptionsContent.tsx#L138) `["subscriptions", code]` 同类错误 → 删除后列表不刷新。
- [settings/tasks/page.tsx#L43-L45](file:///home/collyn/projects/InvestRing/frontend/src/app/settings/tasks/page.tsx#L43) runTask 后漏 invalidate `["tasks","executions"]` → 执行历史不刷新。

**P1-18 移动端鉴权无水合等待。** [app/m/layout.tsx](file:///home/collyn/projects/InvestRing/frontend/src/app/m/layout.tsx) 直接判断 `isAuthenticated` 并跳转，而 PC 侧 [MainLayout.tsx#L18-L44](file:///home/collyn/projects/InvestRing/frontend/src/components/layout/MainLayout.tsx#L18-L44) 已有完整 hydrated 处理（注释引 issue #68）却未同步到移动端 → 移动端已登录用户刷新可能闪跳登录页。与 P0-1 同源，一并修复。

## 其余契约不一致

**P1-19 更新类型字段与后端不符，用户操作被静默丢弃。**
- [types/trade.ts#L37-L45](file:///home/collyn/projects/InvestRing/frontend/src/types/trade.ts#L37-L45) `TradeUpdate` 有 `confirm_date`、`status`，后端 `TradeUpdate` 只接受 `shares/amount/price/fee/actual_amount/trade_date/notes` → 多出字段被 Pydantic 忽略（用户以为改了状态实际没改）；前端反缺后端支持的 `trade_date`。
- `SubscriptionUpdate` 同样多了 `confirm_date`、`status`。
- [api/trade.ts#L21-L22](file:///home/collyn/projects/InvestRing/frontend/src/lib/api/trade.ts#L21-L22) confirm 把 `confirm_date`/`price` 放 body，后端 [trades.py#L130-L134](file:///home/collyn/projects/InvestRing/backend/app/routers/trades.py#L130-L134) 定义为 query → 参数静默丢弃，“补录确认价/日期”能力被封死（当前 UI 未传参，属潜伏）。

**P1-20 其余类型缺口（影响功能可见性）。**
- `SnapshotStatusResponse` 缺 `negative_cash_platforms` → 负现金平台预警不可见；`SnapshotGenerationResult`/`RecalculationPortfolioResult`/`SnapshotGenerateNextResult` 均缺 `warnings` → 快照生成警告全部丢失。
- `ShareChangeEventCreate` 缺 `entitlement_shares`、`cash_product_code`（现金分红落地产品，业务必需）、`event_source`、`parent_event_id`；`Update` 多了后端不接受的 `status`。
- `ProductCreate` 缺 `data_source` → 新建产品无法选数据源。
- [types/log.ts](file:///home/collyn/projects/InvestRing/frontend/src/types/log.ts) 字段名大面积错位，且把真实字段注释成“历史兼容”，方向颠倒：`user_code`→应为 `investor_code`、`ip`→`ip_address`、`message`→`error_message`、`stack`→`error_stack`、`path`→`request_path`、`success`→`status`+`failure_reason`、`cron`→`cron_expr`；`ScheduledTask.id` 标为必填但后端主键是 `code`（无 id 列），还缺 `last_run_status`/`next_run_at`。
- `market` 路径参数问题：[api/product.ts#L23,L26,L31,L38](file:///home/collyn/projects/InvestRing/frontend/src/lib/api/product.ts#L23) 用 `` `${code}/${market || ""}` `` → market 缺省时生成 `/products/510300/` 尾部空段（404/307）；[#L17](file:///home/collyn/projects/InvestRing/frontend/src/lib/api/product.ts#L17) `get` 用 query 传 market 而后端是路径参数 → market 被忽略，恒走自动解析分支，LOF 必抛 `MARKET_AMBIGUOUS`。
- 前端调用后端不存在的端点：`GET /auth/me`（`useCurrentUser`，无调用方）、`POST /portfolios/{code}/batch-rebalance`（`useBatchRebalance`，无调用方）—— 目前是死代码，启用即坏。
- 已核对无误：迁移 0005 的 `cash_amount`/`price_date`/`calendar_date` 前端均已用新名；snapshots 的 `/api/v1` 前缀、cash-transfer 三端点路径、investor/platform/portfolio/subscription/trade 的 CRUD 路径均正确；`EventType` 6 值、`TransactionStatus`、`Role` 枚举与后端一致。

## 布局

**P1-21 窄视口下表格横向溢出。** 实测（视口 575px，PC 页面）：`/portfolio/{code}/trades` scrollWidth 835（溢出 260px）、`/portfolio/{code}/subscriptions` 758、`/portfolio/{code}/positions` 739、`/products` 713。这些页面在移动端复用同一表格（P0-8 影响范围内）→ 移动端体验受损。dashboard/investors/platforms 无溢出。1280px 宽度下 PC 布局正常。

---

# P2 —— 坏味道 / 死代码 / 工程治理

**P2-1 超大页面组件承载全部业务逻辑。** 7 个 PC 页面把 mutation、Dialog、表单状态全部内联：`positions/page.tsx` 642 行（3 个内联 mutation + 3 个 Dialog）、`products` 490、`snapshots` 484、`share-change-events` 483、`settings` 450、`investors` 284、`platforms` 263。违背项目“shared 组件 + hooks”策略，且是 P1-17 三个刷新 bug 的共同根因。

**P2-2 PC / 移动端复制粘贴。** `m/portfolio/[code]/positions/page.tsx` L47-127 与 PC 版 L66-175 逐行复制（“更新非净值资产”完整链路、platforms 查询、总市值 reduce）；组合详情页与 dashboard 亦有重复渲染块。P1-4 的配色漂移已经证明复制的代价。建议抽 `usePositionsPageModel(code)` 或 `PositionsContent`（variant 模式）。

**P2-3 死代码约 780 行（全仓 grep 确认零引用）。**

```
components/desktop/Sidebar.tsx (146)   components/desktop/DataTable.tsx (123)
components/desktop/SplitPane.tsx (65)  components/mobile/ActionSheet.tsx (58)
components/mobile/CardStack.tsx (34)   components/charts/AllocationPie.tsx (62)
components/charts/ReturnChart.tsx (48) components/shared/TradeForm.tsx (204)
components/shared/StatCard.tsx (39)
```

其中 `desktop/Sidebar.tsx` 与在用的 `layout/Sidebar.tsx` 构成双版本菜单配置（两处都含 P0-7 的死链）。`layout/MobileNav.tsx` 与 `mobile/BottomNav.tsx` 职责重叠。

**P2-4 未使用依赖 sonner。** `package.json` 声明 `sonner: ^2.0.0`，全仓零引用；实际用自研 76 行 `components/ui/ToastContainer.tsx` + uiStore。二选一并删除另一方。

**P2-5 死 api 模块与未使用 hook 导出。** `notificationApi`、`logApi` 全模块无消费方（见 P0-7、P1-16）；未使用的 hook 导出：`useLogout`、`useCurrentUser`、`useAuthGuard`、`useCashTransfer.ts` 全部、`useTrade`、`useUpdateTrade`、`useBatchRebalance`、`useSubscription`、`useAvailableCash`。

**P2-6 hooks 覆盖缺口。** `lib/api/` 16 个模块 vs `hooks/` 11 个，缺 `useShareChangeEvent`、`useTask`、`useSystem/useDataSource`、`useNotification`、`useLog` → 对应页面全部内联 useQuery/useMutation。

**P2-7 queryKey 命名不一致。** 主流 `[复数小写, "list", params]`，例外：`["shareChangeEvents", code]`（唯一 camelCase）、`["product-prices"]`、`["data-source-config"]`、`["trading-calendar"]`。`products` 页自造 `["products","list"]` 与 `useProduct.ts` 的 key 并存 → 同一数据两套缓存互不 invalidate。建议集中 `lib/queryKeys.ts` 工厂。

**P2-8 `lib/utils.ts`（292 行）职责混杂。** cn + 5 个日期 + 5 个金额格式化 + 3 个涨跌色 + sleep/generateId/truncateText/deepClone/isWeekend/formatMarketName。建议拆 `lib/format.ts` / `lib/colors.ts` / `lib/misc.ts`；`deepClone` 用 `JSON.parse(JSON.stringify())` 会丢 Date/undefined，应换 `structuredClone`。

**P2-9 格式化逻辑绕过 utils 重复实现。** `dashboard` L74/L108/L195、`m/dashboard` L130 用 `toLocaleString`；`TradesContent` L337、`SubscriptionsContent` L373 用 `price?.toFixed(4)`；`portfolio/[code]` L320 用 `.toFixed(2)`；`settings/tasks` L220 自写耗时格式化；`settings` L159-163 内联 `getWeekDay`。缺 `formatShares`（2 位）/`formatNav`（4 位）统一工具，精度靠调用点手写参数维持。

**P2-10 精度口径与后端不完全一致。** 后端份额 `Numeric(15,2)`、净值/价格 `(10,4)`、金额 `(15,4)`。前端 `formatNumber`/`formatCurrency` 默认 2 位 → 金额展示被四舍五入到分，与 CLI/后端对账会出现“差一点”。`positions/page.tsx#L604` 用 `formatCurrency(unit_price)` 展示净值（2 位 + ¥ 符号，应为 4 位无货币符号）。`share-change-events/page.tsx#L349` 份额输入 `step="0.0001"` 但后端 `shares_change` 是 2 位 → 输入 4 位小数被静默量化，无提示（其余份额输入 `step=0.01` 正确）。金额输入普遍 `step=0.01`（后端支持 4 位）属保守，无功能损害。
表单方向已核对正确：申购输金额 / 赎回输份额、买入输金额 / 卖出输份额。

**P2-11 原生 `confirm()` 残留 5 处。** `products` L132、`investors` L100、`platforms` L124、`snapshots` L125、`settings/tasks` L82 —— 与 `TradesContent`/`SubscriptionsContent` 的 AlertDialog 模式不一致，移动端 WebView 体验差。

**P2-12 `Dialog modal={false}` 7 处。** `positions` L373/L442、`snapshots` L300/L402、`share-change-events` L213、`TradesContent` L165、`SubscriptionsContent` L199 —— 无遮罩、焦点不圈闭、可穿透误操作背后表格。若无拖拽需求应恢复默认。

**P2-13 其他实现细节。**
- `snapshots/page.tsx` L324-326 `key={idx}`。
- 全量 `'use client'`，零 RSC/SSR 收益；`app/page.tsx` 用 useEffect 跳转，而 middleware L14-17 已对 `/` 做服务端重定向 → 双重跳转 + 首屏白屏一帧。
- `BottomNav`（[#L17-L28](file:///home/collyn/projects/InvestRing/frontend/src/components/mobile/BottomNav.tsx#L17-L28)）与 `MobileNav` 硬编码 PC 路径（`/dashboard` 等），移动 UA 下每次点击都触发一次 middleware 307 重定向到 `/m/*`，功能可用但多一跳、URL 闪烁；`isActive` 判断也因此在 `/m/*` 路径下永不命中 → 底部导航高亮失效。
- `settings/page.tsx` L433 硬编码 “Next.js 14”（实际 15）。
- 状态徽章中文映射（启用/禁用、成功/失败/运行中、draft/active/closed）在 ≥4 处以内联三元重复，建议 `lib/constants.ts` + `<StatusBadge>`。
- 登录页 `window.location.href` 硬跳转（为让 middleware 重读 cookie，可理解但需注释）。
- providers 未设全局 `retry`/`refetchOnWindowFocus` 默认策略。

**P2-14 前端未纳入 CI 门禁。** [.github/workflows/ci.yml](file:///home/collyn/projects/InvestRing/.github/workflows/ci.yml) 注释写“仅后端测试（前端未部署，暂不纳入 CI 门禁）”，但前端已容器化部署（deploy.yml 有 frontend 镜像构建）。本次发现的 P0-2（`tasks.map` 崩溃）、P1-19/20（类型字段错位）本可由 `tsc --noEmit` + 一次冒烟 E2E 拦住。

**P2-15 本地开发环境缺 Node.js。**（已解决，2026-07-30）WSL 内已通过 nvm 安装 Node v24.18.1 并完成 `npm install`，lint/tsc/build 均可本地执行；项目 Node 运行时已同步升级至 24（Dockerfile `node:24-alpine`、`@types/node ^24`、`engines.node >=24`、`.nvmrc`）。

**P2-16 E2E 覆盖近乎为零。** 仅 `e2e/auth.spec.ts`。建议优先补：① 移动端 `/m/login` 登录冒烟（可拦住 P0-1）；② `/settings/tasks` 页面渲染（拦住 P0-2）；③ 组合详情 → 持仓 → 交易创建 → 列表刷新（拦住 P1-17）；④ 改密码/编辑投资人请求方法与 URL 断言（拦住 P0-3/P0-4）。

## 后端端点前端未使用清单（约 22 个，供功能规划参考）

```
POST   /api/auth/logout                        GET  /api/portfolios/{code}/nav-history
GET    /api/portfolios/{code}/returns          GET  /api/portfolios/{code}/cash-flow
GET    /api/products/{code}/{market}           GET  /api/trading-calendar/next
GET    /api/trading-calendar/prev              GET  /api/trading-calendar/is-open
GET    /api/market-data/.../nav-coverage       GET  /api/trades/{id}/preview
POST   /api/share-change-events/{id}/unconfirm GET  /api/positions/{id}
DELETE /api/positions/{id}                     GET  /api/system/tasks/{code}
GET    /api/system/tasks/{code}/logs           GET  /api/system/notifications (+read, read-all)
POST   /api/v1/snapshots/catch-up              POST /api/v1/snapshots/generate-next
DELETE /api/v1/snapshots/{code}/bulk/{from}    POST /api/portfolios/{code}/cash-transfer/{group}/confirm
GET    /api/portfolios/{code}/cash-transfers   POST /api/sync-jobs/price (+ 2 个 job 查询端点)
```

---

# 建议修复路线

**第一批（小改动、立刻见效）**
1. P0-1 `/m/login` 移出鉴权守卫 + P1-18 补水合等待 —— 恢复移动端可用性。
2. P0-3 改 `PUT`；P0-4 改 mutate 传参；P0-2 `taskApi.list` 解包分页；P0-6 端点改 `/{code}/logs` 或移除；P0-5 移除删除组合入口；P0-7 删除“日志”导航项（或补页面）。
3. P1-7 401 改调 `authStore.logout()`；P1-13 `handleApiError` 加字符串 detail 分支。

**第二批（架构收敛，一次根治多个 bug）**
4. 建 `lib/queryKeys.ts`，补齐缺失 hooks，消灭页面内联 mutation —— 同时修掉 P1-17 三个刷新 bug 与 P2-7。
5. P0-8 把 6 个 PC 页面内容抽为 shared Content 组件，移动端改真薄壳；`MobileLayout` 只保留一层。顺带处理 P2-2 持仓页重复与 P1-4 配色漂移（统一走 `getReturnColorClass`）。
6. P1-11 `ApiException` 保留 `details`，为 `MARKET_AMBIGUOUS`/`DUPLICATE_TRADE`/`force_cover` 三处加交互恢复。

**第三批（数据正确性与功能闭环）**
7. P1-1 持仓盈亏三列（后端补派生字段）；P1-2 接 `nav-history`；P1-3 接 `/returns`；P1-5 数据源表单回填 + akshare 独立 PUT。
8. P1-15 补现金转移 confirm/list UI；P1-16 通知入口；P1-19/20 类型字段对齐。
9. P1-8 加 `<AdminGuard>`。

**第四批（工程治理）**
10. ~~P2-15 WSL 装 Node~~（已完成，Node 24）；P2-14 CI 加 `tsc --noEmit` + `eslint` + 冒烟 E2E；P2-3/4/5 删死代码与未用依赖，加 `knip`/`ts-prune` 防再生（lint 的 21 条 no-unused-vars 告警可一并清零）；P2-16 补 4 条关键 E2E。
11. P2-8/9/10 拆 utils、补 `formatShares`/`formatNav`，统一精度口径。

# 附：环境遗留

- 测试组合 `TESTQA01`（QA测试组合）因 P0-5 无法删除，仍存于生产环境，需后端或数据库侧清理。
- 测试投资人 `TEST_QA1` 已成功删除。
- 实测截图存于 `/tmp/`（`test1_password_405.png`、`test2_investor_edit_failed.png`、`test3_portfolio_delete_405.png`、`test4_non_trading_day.png`、`test5_date_before_snapshot.png`、`test6_tasks_crash.png`、`14_settings_tasks_error.png`、`15_settings_logs_404.png`、`11_portfolio_nav_history.png`、`12_portfolio_positions.png`、`13_portfolio_trades.png` 等），系临时目录，需要长期留存请及时转移。
