# 实施计划：#125 申赎筛选 + #126 调仓筛选与结对显示（合并实施）

> 合并为一个 PR 的理由：两 issue 共享同一套新基件（`date-range-picker`、分页）与筛选栏模式（visual-spec §9/§10/§11/§14），后端改动同构（list 端点补参数 + 过滤下沉 service），分开实施会产生中间态返工。
>
> **前置状态（已核实）**：#124 已合入 dev（PR #149，`NameCodeCell` 主次双行已在 SubscriptionsContent 落地）；visual-spec 补充已合入 dev（PR #148，§8 结对行/§9 筛选栏/§10 日期区间/§11 分页/§14 局部加载态为本计划的 UI 依据）。
>
> **已确认决策（11 条，本计划不重新讨论）**：① 服务端筛选；② pending 按预计确认日参与确认日期筛选、UI 标注「预计」；③ ir-cli 同步优化（openapi 重导、契约重跑、`sub/trade list` 加参、删本地筛 pending 绕路）；④ 新基件按规范落地；⑤ 即时查询、单页 20、默认最近 1 年；⑥ `start > end` 返回 422；⑦ 过滤逻辑下沉 service；⑧ 结对显示规则全集；⑨ `Trade` 类型补 `transfer_group`；⑩ 排序改 `apply_date`/`trade_date DESC, id DESC`；⑪ 排序键加 `transfer_group` 使同组相邻。

---

## 1. 改动地图（按层）

| 层 | 文件 | 动作 |
|---|---|---|
| backend | `app/services/subscription_service.py` | 新增 `list_subscriptions()` |
| backend | `app/services/trade_service.py` | 新增 `list_trades()` |
| backend | `app/routers/subscriptions.py` | `GET /api/subscriptions` 加 7 个查询参数，改调 service |
| backend | `app/routers/trades.py` | `GET /api/trades` 加 9 个查询参数，改调 service |
| backend | `tests/integration/test_subscriptions.py` | 新增筛选测试类 |
| backend | `tests/integration/test_trades.py` | 新增筛选测试类 |
| backend | `openapi.json` | 重导（仅两 GET 端点新增 query params） |
| ir-cli | `ir_cli/commands/subscriptions.py` | `list` 加 7 个 option |
| ir-cli | `ir_cli/commands/trades.py` | `list` 加 9 个 option |
| ir-cli | `ir_cli/commands/portfolios.py` | `context` 改服务端 `status=pending` 过滤，删本地筛绕路 |
| ir-cli | `ir_cli/response_fields.py` | 重跑生成器（预期无 diff，见 §5 风险 3） |
| ir-cli | `CLI_MANUAL.md` | 补新 option 说明 |
| frontend | `src/components/ui/date-range-picker.tsx` | **新建**（规范 §10） |
| frontend | `src/components/ui/calendar.tsx` | range_middle 配色对齐规范 §10（`bg-accent` → `bg-success-soft`） |
| frontend | `src/components/ui/pagination.tsx` | **新建** shadcn 原语（规范 §11） |
| frontend | `src/components/shared/PaginationBar.tsx` | **新建** 业务分页条（双端形态差异内聚） |
| frontend | `src/lib/api/subscription.ts` / `trade.ts` | list 参数类型扩展并导出 |
| frontend | `src/hooks/useTrade.ts` | 两个 list hook 参数类型扩展 + `keepPreviousData` |
| frontend | `src/types/trade.ts` | `Trade` 补 `transfer_group?: string` |
| frontend | `src/lib/tradePairs.ts` | **新建** 结对分组纯函数 |
| frontend | `src/components/shared/SubscriptionsContent.tsx` | 筛选栏 + 分页 + 「预计」标注 |
| frontend | `src/components/shared/TradesContent.tsx` | 筛选栏 + 分页 + 结对渲染 |

无 DB 迁移、无新依赖（`react-day-picker@^10` / `date-fns@^3` 已就位）。

---

## 2. 阶段划分

| 阶段 | 内容 | 产出验证 |
|---|---|---|
| 1 | 后端：两个 service list 函数 + 两个 router 端点 + pytest | `pytest tests/integration/test_subscriptions.py tests/integration/test_trades.py` 全绿 |
| 2 | 契约与 CLI：openapi.json 重导、gen_response_fields 重跑、CLI 三文件改动 + CLI_MANUAL | `python ir-cli/scripts/gen_response_fields.py --check` 通过；`ir sub list --status pending` 手验 |
| 3 | 前端基件：calendar range token、date-range-picker、pagination 原语 + PaginationBar | `npm run lint && npm run build` 0 error |
| 4 | SubscriptionsContent 接入筛选/分页/「预计」 | 页面手验（§6 清单） |
| 5 | TradesContent 接入筛选/分页/结对 | 页面手验（§6 清单） |
| 6 | 全量验证 + PR | 后端 pytest 全量、前端 lint/build、ir-cli 测试、CI 全绿 |

阶段 1→2→3 严格顺序；4、5 可并行但建议 4 先 5 后（4 验证筛选栏模式后 5 复用）。

---

## 3. 后端改动明细（阶段 1）

### 3.1 `app/services/subscription_service.py` — 新增 `list_subscriptions`

```python
def list_subscriptions(
    db: Session, *,
    portfolio_code: Optional[str] = None,
    investor_code: Optional[str] = None,   # router 已叠加 viewer 强制值
    status: Optional[str] = None,
    sub_type: Optional[str] = None,
    platform_code: Optional[str] = None,
    apply_date_start: Optional[date] = None,
    apply_date_end: Optional[date] = None,
    confirm_date_start: Optional[date] = None,
    confirm_date_end: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Subscription], int]:
```

要点：

- **区间校验**：`apply/confirm` 两组各自校验 `start > end` → `raise BusinessError("INVALID_DATE_RANGE", f"start_date ({s}) 不能晚于 end_date ({e})", http_status=422)`——直接复用 `market_data_service.py:105` 的既有模式（该错误码已存在于代码库，非新造）。
- **闭区间**过滤：`apply_date >= start`、`apply_date <= end`，confirm 同理。
- **排序**：`order_by(Subscription.apply_date.desc(), Subscription.id.desc())`（决策⑩）。
- **返回**：`(items, total)`，`total` 为过滤后 count（分页前）。
- **docstring 注明语义**：pending 记录 `confirm_date` 为**预计确认日**（创建时按 T+1 设定、unconfirm 时重算保持非空），确认日期区间筛选对 pending 命中预计值（决策②）。
- 不 commit、不抛 HTTPException（分层约定 §4.1）。

### 3.2 `app/services/trade_service.py` — 新增 `list_trades`

参数：`portfolio_code / status / trade_type / product_code / market / platform_code / trade_date_start / trade_date_end / confirm_date_start / confirm_date_end / page / page_size`。

要点：

- 区间校验同 3.1（422 `INVALID_DATE_RANGE`）。
- `product_code` 与 `market` 独立可选：都给则精确过滤（LOF 一码多市场场景）；只给 `product_code` 则跨市场全匹配（与 #126 设计一致）。
- **排序**：`order_by(Trade.trade_date.desc(), Trade.transfer_group, Trade.id.desc())`——`transfer_group` 入排序键使同组两腿大概率同页相邻（决策⑪，缓解跨页拆对；同组两腿同事务插入 id 连续，此为双保险）。
- docstring 注明：trades 无 viewer 过滤（组合级操作，保持现状语义，不在本 PR 引入权限变化）。

### 3.3 `app/routers/subscriptions.py` — `get_subscriptions` 改造

- 新增 7 个 `Optional` query 参数（`status / sub_type / platform_code / apply_date_start / apply_date_end / confirm_date_start / confirm_date_end`，date 类型由 FastAPI 自动解析 `YYYY-MM-DD`）。
- **viewer 限制保持在 router**：非 admin 时强制 `investor_code = current_user.code`（覆盖请求传参），再调 `list_subscriptions(...)`——权限归适配层、过滤归 service。
- 响应形状不变：`{"items","total","page","page_size"}`，**不加 response_model**（现契约如此，CLI 契约依赖 POST 端点的 schema，见 §5 风险 3）。

### 3.4 `app/routers/trades.py` — `get_trades` 改造

- 新增 9 个 `Optional` query 参数（`status / trade_type / product_code / market / platform_code / trade_date_start / trade_date_end / confirm_date_start / confirm_date_end`）。
- 无 viewer 过滤（保持现状），直接调 `list_trades(...)`。

### 3.5 后端测试

`tests/integration/test_subscriptions.py` 新增 `TestListSubscriptionFilters`：

| 用例 | 断言 |
|---|---|
| `test_filter_by_status` | 造 pending+confirmed+cancelled 各 1，分别过滤只回目标状态 |
| `test_filter_by_sub_type_and_platform` | `sub_type=redeem` + `platform_code` 组合为交集 |
| `test_filter_apply_date_range_closed` | 边界日记录**包含**（闭区间） |
| `test_filter_confirm_date_includes_pending_expected` | pending 记录按预计确认日命中区间（决策②） |
| `test_inverted_range_returns_422` | `apply_date_start > end` → 422 `INVALID_DATE_RANGE`；confirm 组同理 |
| `test_sort_apply_date_desc` | 乱序造数，断言 `apply_date` 降序、同日期 id 降序 |
| `test_viewer_restriction_with_filters` | viewer 带 `status` 过滤仍只见自己记录（权限 × 筛选叠加） |

`tests/integration/test_trades.py` 新增 `TestListTradeFilters`：状态/类型/平台/日期区间/422/排序同上；另加：

| 用例 | 断言 |
|---|---|
| `test_filter_product_code_only_matches_all_markets` | 仅 `product_code` 时 LOF 两市场都命中 |
| `test_filter_product_code_with_market_exact` | `product_code + market` 精确过滤 |
| `test_sort_groups_adjacent` | 同 `transfer_group` 两腿在结果中相邻（决策⑪） |

测试写法沿用既有惯例：`factories.py` 的 `create_portfolio/create_investor/create_platform/create_subscription` + `ensure_trading_day` + `client.get(..., headers=admin_headers)`。

---

## 4. ir-cli 改动明细（阶段 2）

### 4.1 openapi.json 重导

仓内惯例需运行中的后端：`cd backend && uvicorn app.main:app` 后 `python export_openapi.py`（或离线单行 `python -c "import json; from app.main import app; json.dump(app.openapi(), open('openapi.json','w'), ensure_ascii=False, indent=2)"`，二者产出须一致）。**diff 自查**：仅两个 GET 端点的 `parameters` 新增，无其他漂移。

### 4.2 `python ir-cli/scripts/gen_response_fields.py` 重跑

响应 schema 未动（`TradeResponse`/`SubscriptionResponse` 来自 POST 端点），**预期 `response_fields.py` 无 diff**；随后 `--check` 自验。

### 4.3 `ir_cli/commands/subscriptions.py::list`

新增 option（均 `Optional`，经 `build_body` 透传）：
`--status` / `--type`(sub_type) / `--platform-code` / `--apply-date-start` / `--apply-date-end` / `--confirm-date-start` / `--confirm-date-end`。docstring 注明「确认日期对 pending 为预计确认日」。

### 4.4 `ir_cli/commands/trades.py::list`

新增：`--status` / `--type`(trade_type) / `--product-code` / `--market` / `--platform-code` / `--trade-date-start` / `--trade-date-end` / `--confirm-date-start` / `--confirm-date-end`。

### 4.5 `ir_cli/commands/portfolios.py::context` — 删绕路

```python
# 现状（删）：get_all 全量拉取后 [s for s in subs if s.get("status")=="pending"]
# 改为：
subs = client.get_all("/api/subscriptions", params={"portfolio_code": code, "status": "pending"})["data"]
trades = client.get_all("/api/trades", params={"portfolio_code": code, "status": "pending"})["data"]
```

删除「后端 list 端点不支持 status 过滤」注释与本地 filter 列表推导，`project_fields(...)` 摘要投影保留。

### 4.6 `ir_cli/utils.py` ENUMS（可选增强）

`build_body` 不做枚举校验（枚举校验挂在写路径的 `resolve_body`）。新增 `--status` 属 list 路径 → 默认无客户端校验。可选：ENUMS 加 `"status": ("pending","confirmed","cancelled")` 并在 list 参数构造处复用校验函数；**不做也不阻断**（后端对非法 status 返回空集，行为合理）。实施时若 5 分钟能挂上就带上，否则不做并在 PR 说明。

### 4.7 其他

- `CLI_MANUAL.md`：两 list 命令补新 option 表格行（文档随代码同行，AGENTS.md §8.5-5）。
- `ir schema` 经 typer 反射自动感知新 option，无需改 `schema.py`。
- 跑 `PYTHONPATH=ir-cli .venv/bin/python -m pytest ir-cli/tests/ -q`（`test_schema.py` 若有命令结构断言需同步）。

---

## 5. 前端改动明细（阶段 3-5）

### 5.1 基件：`ui/calendar.tsx`（微调）

range 相关默认样式对齐规范 §10：`range_middle` 由 `bg-accent` 改为 `bg-success-soft text-success-foreground`（`classNames.range_middle` 与 `CalendarDayButton` 的 `data-[range-middle=true]:` 两处）。range_start/end 已是 `bg-primary text-primary-foreground`，不动。**无现存 range 使用方，改动安全。**

### 5.2 基件：`ui/date-range-picker.tsx`（新建，规范 §10）

```tsx
interface DateRangePickerProps {
  value?: { from?: Date; to?: Date };   // react-day-picker DateRange
  onChange?: (range: { from?: Date; to?: Date } | undefined) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  numberOfMonths?: 1 | 2;               // 调用方按端传：桌面 2 / 移动 1
}
```

- 触发按钮继承单选先例：outline + `CalendarIcon` + 占位 `text-muted-foreground` + 右侧 X 清空；文案 `YYYY-MM-DD ~ YYYY-MM-DD`，移动端不换行溢出省略。
- **快捷选项 8 项**（date-fns 实现，区间语义在此定死）：

  | 选项 | from | to |
  |---|---|---|
  | 本月 | `startOfMonth(now)` | `now` |
  | 本季度 | `startOfQuarter(now)` | `now` |
  | 今年 | `startOfYear(now)` | `now` |
  | 去年 | `startOfYear(subYears(now,1))` | `endOfYear(subYears(now,1))` |
  | 最近7天 | `subDays(now,6)` | `now` |
  | 最近1个月 | `subMonths(now,1)` | `now` |
  | 最近1年 | `subYears(now,1)` | `now` |
  | 最近3年 | `subYears(now,3)` | `now` |

  桌面置日历左侧竖排文本按钮、移动置顶部横向滚动；选中态 `bg-success-soft text-success-foreground`。
- **联动**：手选区间与某快捷项完全一致→保持其选中，否则解除全部快捷项选中态（比较用 `isSameDay`）。
- **弹层**：选完起止即关；不设「确定」；清空只靠 X。**不启用** `showTradingDays`（规范 §10 边界）。

### 5.3 基件：`ui/pagination.tsx`（新建，shadcn 原语）

`Pagination / PaginationContent / PaginationItem / PaginationLink / PaginationPrevious / PaginationNext / PaginationEllipsis` + 导出纯函数 `buildPageItems(page, totalPages): (number | "ellipsis")[]`（≤7 全显；否则首末页 + 当前 ±1 + 省略号）。

### 5.4 业务件：`shared/PaginationBar.tsx`（新建，规范 §11）

props：`{ page, pageSize, total, variant: "desktop" | "mobile", onPageChange, onPageSizeChange }`。

- 桌面：左「共 N 条」`text-xs text-muted-foreground` + 右侧页码原语 + 每页条数 Select（20/50/100）。
- 移动：「上一页 / 第 x / N 页 / 下一页」，无页码与条数切换。
- 整行右对齐；`total <= pageSize` 时整bar不渲染。

### 5.5 API/hooks/types

- `lib/api/subscription.ts`：导出 `SubscriptionListParams`（现有 4 字段 + `status / sub_type / platform_code / apply_date_start / apply_date_end / confirm_date_start / confirm_date_end`），`list(params?: SubscriptionListParams)`。axios 默认丢弃 `undefined` 值——空筛选不传参 ✓。
- `lib/api/trade.ts`：同理导出 `TradeListParams`（+ `status / trade_type / product_code / market / platform_code / 4 个日期`）。
- `hooks/useTrade.ts`：`useSubscriptionList` / `useTradeList` 参数类型换为上述导出类型；加 `placeholderData: keepPreviousData`（react-query v5.62 已就位）——配合规范 §14 局部加载态保留旧数据。`queryKey` 已含 params，筛选变更自动 refetch ✓。
- `types/trade.ts`：`Trade` 补 `transfer_group?: string`（决策⑨）。

### 5.6 `lib/tradePairs.ts`（新建，结对纯函数）

```ts
export type TradeRow =
  | { kind: "pair"; main: Trade; sub: Trade }     // 基金腿主 + 现金腿子；或转移 sell 主 buy 子
  | { kind: "single"; trade: Trade };

export function groupTradeRows(trades: Trade[]): TradeRow[]
```

规则（决策⑧，顺序敏感）：

1. 按 `transfer_group` 分组（保持传入顺序 = 后端排序序）。
2. `sub_` 前缀组 → 恒 `single`（申赎现金腿，主体在申赎页）。
3. 组内恰 2 条且 1 条 `product_code !== "CASH"` + 1 条 `"CASH"` → `pair`（基金主、现金子）。
4. 组内恰 2 条均为 CASH → `pair`（`sell` 主、`buy` 子；现金跨平台转移）。
5. 其余（组内 1 条=配对腿被筛选/分页排除的孤儿、空组、异常多条）→ 全部 `single` 回退。

子行派生数据：`{ label: "现金扣款" | "现金到账", platformCode, signedAmount }`——买入配对=扣款（`-`）、卖出配对=到账（`+`）；符号展示层推导不回写（规范 §8）。**不展示 `transfer_group` 编码**。

### 5.7 `SubscriptionsContent.tsx`（阶段 4）

- **筛选状态**：`useState` 持有 `{ status?, subType?, investorCode?, platformCode?, applyRange?, confirmRange? }` + `page` + `pageSize`；`applyRange` 初始值 = 最近 1 年（决策⑤，`useState(() => …)` 惰性初始化避免每渲染重算）。
- **筛选栏**（规范 §9）：桌面 `flex flex-wrap gap-2`、控件 `h-9`、顺序=申购日期区间→确认日期区间→状态→投资人→平台→类型；placeholder「全部状态/全部投资人/全部平台/全部类型」；非默认筛选存在时行尾「重置」ghost 按钮（恢复默认集）。移动端：「筛选」按钮 + 激活计数 Badge（`default` variant）+ 折叠面板内 `grid-cols-1` 纵排。
- **下拉用 `ui/select`**（规范 §13 复用红线；表单对话框内的原生 `<select>` 不在本 PR 收敛，避免扩面）。
- **查询接线**：filters→`useSubscriptionList(params)`（日期区间转 `apply_date_start/end` 等；空区间=undefined 不传）；筛选变更 `setPage(1)`。
- **「预计」标注**（决策②）：确认日期单元格 `sub.status === "pending"` 时渲染日期 + 次行 `text-xs text-muted-foreground`「预计」。
- **加载态**：`isLoading` 首载走 `LoadingState`；`isFetching` 局部刷新时表格容器 `opacity-50` + 右上角 `Loader2`（规范 §14，配合 keepPreviousData）。
- **空态**：`total===0 且无筛选` → 「暂无申请记录」（现状保留）；`有筛选` → 「无符合筛选条件的记录」+ 内嵌「重置筛选」入口（规范 §8 变体②，`EmptyState` 的 `action` 位）。
- **分页**：`PaginationBar` 置于表格 Card 内表格下方；`pageSize` 默认 20。
- 保留 #124 的 `NameCodeCell` 投资人/平台列不变。

### 5.8 `TradesContent.tsx`（阶段 5）

- 筛选栏同构：交易日期区间（默认最近 1 年）→确认日期区间→状态→产品→平台→类型。
- **产品下拉**：选项 key `code|market`，文案单行 `name (code)`，一码多市场（LOF）时 `name (code · 市场名)`（`formatMarketName`）；选中后按 `product_code(+market)` 传参。
- **结对渲染**：`trades → groupTradeRows()` →
  - `pair`：主行正常渲染且 `border-b-0`；子行首列 `pl-8`、整行 `bg-muted/50`、内容 `text-xs`，产品列渲染「现金扣款 · 平台name」/「现金到账 · 平台name」，金额列 `text-foreground` 带 `-`/`+`（`formatCurrency` 后手工前缀符号——注意 `formatCurrency` 不自带符号，此处符号为语义修饰非数值一部分），操作列空；子行无 hover/点击。
  - `single`：维持现状渲染；CASH 孤儿行产品列「现金 · 业务来源」（来源由 `transfer_group` 前缀推导：`sub_`→「申购确认」/「赎回确认」需查 subscription？——**简化**：`sub_` 前缀统一显示「现金 · 申赎确认」，裸 uuid 双 CASH 被拆散的单腿显示「现金 · 平台间转移」，其余「现金 · 调仓」；不为此新增接口）。
- 平台列同名映射沿用 #124 模式（`NameCodeCell` 复用——把它从 SubscriptionsContent 提到 `components/shared/` 共用？**决策**：提为 `shared/NameCodeCell.tsx`，两页共用，避免复制）。
- 产品列现有双行（`font-medium` name + `text-sm text-muted-foreground` code）顺手对齐规范 §8：次行改 `text-xs`（存量收敛，规范 §18 原则「改动到该页面时顺手替换」）。
- 「预计」标注、加载态、空态、分页同 5.7。

---

## 6. 测试方案

### 后端（阶段 1 内完成）

- 新增两测试类（§3.5，共约 15 个用例）；
- 回归：`cd backend && .venv/bin/python -m pytest tests/ -q` 全量。

### ir-cli（阶段 2 内完成）

- `PYTHONPATH=ir-cli .venv/bin/python -m pytest ir-cli/tests/ -q`；
- `python ir-cli/scripts/gen_response_fields.py --check`；
- 手验（需本地后端有数据）：`ir sub list --status pending --type redeem`、`ir trade list --product-code X --trade-date-start …`、`ir portfolio context <code>`（pending 聚合仍正确）。

### 前端（阶段 3-6）

- 无单测框架（仓内仅 Playwright E2E，本 PR 不新增 E2E）；`groupTradeRows`/`buildPageItems` 保持纯函数以便日后补测；
- `npm run lint && npm run build` 0 error；
- **人工验收矩阵**（合并 #125/#126 验收断言）：

| # | 断言 | 来源 |
|---|---|---|
| 1 | 进入申赎/调仓页默认按申购/交易日期最近 1 年过滤，快捷项「最近1年」选中 | #125/#126 |
| 2 | 两日期区间组件支持手选（含跨月）+ 8 快捷项点击即填 | #125 |
| 3 | 状态/投资人/平台/类型（申赎）、状态/产品/平台/类型（调仓）各自生效，组合为交集 | #125/#126 |
| 4 | 清空某日期区间即不限该维度；「重置」恢复默认集 | #125 |
| 5 | pending 记录按预计确认日参与确认日期筛选，且该列标注「预计」 | 决策② |
| 6 | 直连后端：`?status=&sub_type=&apply_date_start=…` 结果与前端一致；`start>end` → 422 | #125 |
| 7 | viewer 仅见自己申赎记录（权限×筛选叠加） | #125 |
| 8 | 产品筛选下配对现金腿被排除时基金腿单行回退 | #126 |
| 9 | 基金买入+现金扣款结对：主行基金、子行「现金扣款 · 平台」负金额；卖出同理正金额（含跨平台 `cash_platform_code` 场景） | #126 |
| 10 | 跨平台现金转移结对：sell 主行 buy 子行 | #126 |
| 11 | `sub_*` 单腿不结对，单行显示「现金 · 申赎确认」 | #126 |
| 12 | 页面任何位置不出现 `transfer_group` 编码 | #126 |
| 13 | 翻页跨页拆对时孤儿腿单行、无空白错行；同组相邻排序降低发生概率 | 决策⑪ |
| 14 | 筛选/翻页局部刷新：旧数据保留 + `opacity-50` + 小 spinner，无闪烁 | 规范 §14 |
| 15 | 移动端筛选折叠面板 + 计数 Badge、单月日历、简化分页 | 规范 §9/§10/§11 |
| 16 | `npm run lint && npm run build` 0 error；后端 pytest 全绿；CLI 契约 CI 通过 | #125/#126 |

---

## 7. 风险与备注

1. **排序行为变更**：`created_at DESC` → `apply_date/trade_date DESC`，影响 `ir sub list`/`ir trade list` 既有输出顺序——PR 描述「部署影响」节注明。
2. **跨页拆对**不可根除（页边界正好切开一对时该页出现单行回退）；决策⑪已把概率压到最低，验收断言 13 覆盖。
3. **CLI 契约预期零变化**：响应 schema 未动，`response_fields.py` 应无 diff；若 `--check` 意外失败，先查 openapi.json 是否引入无关漂移（如本地后端版本杂波），不要直接提交陌生 diff。
4. **openapi.json 导出**依赖本地运行后端（`export_openapi.py`），导出后人工核对 diff 仅含两 GET 端点新参数。
5. **`page_size=100` 的 investors/platforms/products 下拉数据**：筛选下拉复用现有全量列表请求，与 #124 同前提（单用户场景数量级远小于 100），不新增搜索式下拉（YAGNI）。
6. **PR 规模控制**：本 PR 已合并两 issue，不再夹带其他收敛（表单原生 `<select>`、`h-10` 表单档维持现状等），评审聚焦筛选与结对。
7. **分支**：`feature/125-sub-trade-filters` 自最新 dev 切出（#124/#148 均已合入）。
