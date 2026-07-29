# 前端 Issue #67/#68/#69 修复 + 导航与日历增强

## 背景与根因结论

| 问题 | 根因 |
|---|---|
| #68 全页加载被踢回 /login（P0） | [MainLayout.tsx](file:///home/collyn/projects/InvestRing/frontend/src/components/layout/MainLayout.tsx) 首帧读取 `isAuthenticated=false`（persist 尚未从 localStorage 水合）即 `router.push("/login")` |
| #69 dashboard 总资产 ¥0.00（P1） | 后端 `GET /api/portfolios` 列表不返回 `total_value`/`cumulative_return`/`investor_count`；前端另调用 5 个后端不存在的端点（404） |
| #67 全部卖出/赎回 | 卖出可用份额已有端点 `GET /positions/portfolio/{code}/product/{product_code}/available-shares`；投资人可用份额 service 已有（`calculate_investor_available_shares`）但**无 REST 端点** |
| 快照管理需点两次 | [portfolio/[code]/page.tsx L206-210](file:///home/collyn/projects/InvestRing/frontend/src/app/portfolio/%5Bcode%5D/page.tsx#L206-L210) 用 `<Link>` 包裹 Radix `TabsTrigger`，首次点击被 Tabs 激活逻辑拦截，未触发导航 |
| 日历无交易日标识 | DatePicker/Calendar 未接入 trading_calendar 数据；前端已有 `systemApi.getTradingCalendar(year)` 封装 |

## 一、后端改动（#69 组合方案 + #67 端点补齐）

### 1. portfolio 列表聚合字段
- `backend/app/services/portfolio_service.py` 新增 `list_portfolios(db, status, page, page_size)`：
  - 分页查询 Portfolio（现有 router 内联逻辑下沉）
  - 每个组合从最新 `portfolio_value_snapshot` 取 `total_value`；`cumulative_return` 复用 `get_returns` 口径（首末 unit_price，百分数值，与 `/returns` 一致）；`investor_count` 取最新快照日 `investor_holding` 中 `shares > 0` 的投资人数
  - 无快照的 draft 组合三字段返回 None/0
- `backend/app/routers/portfolios.py` 的 `get_portfolios` 改为薄适配调用该 service（遵循 AGENTS.md §4.1 分层约定，service 不 commit）

### 2. 新增两个端点（前端已在调用）
均在 `portfolio_service.py` 实现业务、router 薄适配：
- `GET /api/portfolios/{code}/snapshots/latest`：返回最新一条 `portfolio_value_snapshot`（`snapshot_date`/`total_value`/`total_shares`/`unit_price` 等），无快照返回 404（NotFoundError）
- `GET /api/portfolios/{code}/investors`：最新快照日 `investor_holding` join `investor`，返回 `[{investor_code, name, shares}]`

### 3. #67 投资人可用份额端点
- `backend/app/routers/positions.py` 新增 `GET /positions/portfolio/{portfolio_code}/investor/{investor_code}/available-shares`，调用现有 [calculate_investor_available_shares](file:///home/collyn/projects/InvestRing/backend/app/services/position_service.py#L300)，返回 `{portfolio_code, investor_code, available_shares}`（float，2 位小数原样透传）

### 4. 契约同步
- 运行 `backend/export_openapi.py` 重新生成 `backend/openapi.json`
- 运行 `ir-cli/scripts/gen_response_fields.py` 更新 `ir_cli/response_fields.py`（CI 有一致性校验）

### 5. 后端测试
- `backend/tests/integration/` 新增/扩展用例：列表聚合字段（有/无快照）、`snapshots/latest`、`{code}/investors`、投资人 available-shares（含 pending 赎回扣减）

## 二、前端改动

### 1. #68 水合竞态修复（P0）
[MainLayout.tsx](file:///home/collyn/projects/InvestRing/frontend/src/components/layout/MainLayout.tsx)：
- 用 `useAuthStore.persist.hasHydrated()` 初始化本地 `hydrated` state，`useEffect` 中订阅 `onFinishHydration`
- `hydrated === false` 时渲染 loading 占位（不重定向、不渲染 children）；水合完成后再执行鉴权判断与 `router.replace("/login")`
- 移动端 `MobileLayout` 无守卫（middleware cookie 兜底），不需改动

### 2. #69 前端清理（死代码调用移除）
- `frontend/src/lib/api/portfolio.ts`：删除 `portfolioApi.getSnapshots`、`positionApi.getLatest`、`positionApi.getAttribution`（保留 `getLatestSnapshot`、`getInvestors` —— 后端本次补齐）
- `frontend/src/hooks/usePortfolio.ts`：删除 `usePortfolioSnapshots`、`useLatestPositions`、`useAttribution`（无页面消费）
- `frontend/src/hooks/usePosition.ts`：删除重复定义的 `useLatestPositions`、`useAttribution`
- `frontend/src/types/portfolio.ts` 的 `total_value`/`cumulative_return`/`investor_count` 保持声明，由后端列表真实返回

### 3. #67 全部卖出/全部赎回按钮
- `frontend/src/lib/api/portfolio.ts` `positionApi` 新增 `getAvailableShares(portfolioCode, productCode)` 与 `getInvestorAvailableShares(portfolioCode, investorCode)`
- [TradeForm.tsx](file:///home/collyn/projects/InvestRing/frontend/src/components/shared/TradeForm.tsx)：卖出模式下份额输入框旁增加「全部卖出」按钮，点击调 `getAvailableShares`（依赖已填 product_code），将返回的 `available_shares` **原样字符串化填入**（不做任何舍入/格式化）；返回 0 或 product_code 为空时按钮禁用
- [SubscriptionsContent.tsx](file:///home/collyn/projects/InvestRing/frontend/src/components/shared/SubscriptionsContent.tsx)：赎回模式下增加「全部赎回」按钮，依赖已选 investor_code，调 `getInvestorAvailableShares` 填入；可用份额 0 或未选投资人时禁用
- 两处按钮请求中显示 loading，失败 toast 提示

### 4. 快照管理导航双击 bug
[portfolio/[code]/page.tsx L206-210](file:///home/collyn/projects/InvestRing/frontend/src/app/portfolio/%5Bcode%5D/page.tsx#L206-L210)：将 `<Link><TabsTrigger value="snapshots">` 改为 TabsList 外侧同排的普通 `<Link>` + Button（ghost/outline，样式与 tab 视觉协调），不再挂在 Tabs 状态机上，单击即导航

### 5. 日历交易日标识
- 新增 `frontend/src/hooks/useTradingCalendar.ts`：`useTradingCalendar(year)`，react-query 按年缓存（`staleTime` 长缓存），调用现有 `systemApi.getTradingCalendar(year)`
- [date-picker.tsx](file:///home/collyn/projects/InvestRing/frontend/src/components/ui/date-picker.tsx) 增加可选 prop `showTradingDays?: boolean`：
  - 开启时跟踪当前展示月份（`onMonthChange`），按年取交易日历
  - 通过 react-day-picker `modifiers`/`modifiersClassNames` 标注：交易日在日期下方加小圆点（`after:` 伪元素类），非交易日灰显
  - 数据未加载时不标注（不阻塞选择），保持向后兼容（默认关闭）
- 在 TradeForm、SubscriptionsContent、快照管理页三处 DatePicker 开启 `showTradingDays`

## 三、验证与收尾

1. 后端：`pytest backend/tests`（重点新增用例）
2. 前端：`npm run lint` + `next build`（构建期强制 lint + tsc 0 error）
3. 手动/浏览器验证：刷新内页不被踢回登录、dashboard 总资产非 0、组合详情投资人 Tab 有数据、快照管理单击可进、卖出/赎回一键填充提交不报 `INSUFFICIENT_SHARES`、日历圆点标识
4. GitHub 收尾（gh CLI）：验证通过后向 #67/#68/#69 逐个评论根因与修复摘要并关闭；git commit 在用户确认后执行

## 假设
- `cumulative_return` 沿用 `/returns` 的百分数口径（5.23 表示 5.23%），前端 `formatReturnRate` 已按此消费
- attribution（资产归因）功能当前无消费方，本次删除调用、不实现后端端点，后续如需再立 issue