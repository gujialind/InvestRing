# 实施计划：#146 快照管理页重构

> 关联 issue：#146（[feat] 快照管理页重构：补齐后端快照能力 + 历史列表接口 + 双端共享组件）。
> 前置状态（已核实）：#125/#126 已在 `feature/125-sub-trade-filters` 分支落地（后端筛选 816e9df、基件 d228ebc、申赎页 a13ec51、调仓页 3771d35），本计划实施时从**最新 dev** 切 `feature/146-snapshots-refactor`（若 #125/#126 尚未合入 dev，先合或以其为基线，见 §7 风险 1）。
>
> **已确认决策（直接采纳，不重新讨论）**：
> ① 后端新增 `GET /api/snapshots/portfolios/{code}/list`：`start_date`/`end_date` 可选过滤、`limit` 默认 500、`snapshot_date` 倒序、权限 `get_current_user`（与 status 一致）；响应带 `total` 字段防无声截断；
> ② 顺带实现 status 的 `missing_dates`（按 `trading_calendar.is_open=true` 计算首末快照日区间内缺失的交易日，替换恒空数组）；
> ③ 前端新建 `components/shared/SnapshotsContent.tsx`（`variant` + `basePath` 双端共享）、双端薄壳页、AdminGuard；
> ④ 操作区全覆盖：generate-next（主操作，替代错误的"快速更新"）、catch-up、generate（保留预检）、recalculate-async（页面内展示 sync-jobs 进度与终态，移除 force checkbox）、删除（单日仅最新日 + bulk dry_run→confirm 两段式）；
> ⑤ 历史快照表格按 visual-spec §8：日期/净值/涨跌/份额/市值/在途，**涨跌列前端按相邻行计算**；
> ⑥ 视觉合规并入：字号四级收敛、危险按钮 solid `bg-destructive text-white`、数字格式化统一走 `lib/utils.ts`；
> ⑦ 新建 `ui/checkbox` 基件（规范 §13 已登记规格 rounded-sm / 选中 bg-primary）；
> ⑧ 后端同步 recalculate 端点保留不动；
> ⑨ 现状已核实：538 行单文件 page.tsx、无移动端页面。

---

## 0. 现状核实摘要（探索结论，实施时不必重查）

### 后端（`backend/app/routers/snapshots.py`，464 行）

| 端点 | 行号 | 权限 | 前端现状 |
|---|---|---|---|
| `POST /generate` | 35 | admin | 已用（对话框+预检），"快速更新"误用 `generate(今天)` |
| `POST /recalculate` | 73 | admin | 已用（同步，大区间易超时）；**`SnapshotRecalculateRequest` 无 `force` 字段**（schemas/snapshot.py:13-17），前端传了被 Pydantic 丢弃 = 死 UI |
| `POST /recalculate-async` | 117 | admin | 未用；组合不存在 404；冲突 409 `RECALC_JOB_CONFLICT`；返回 `{job_id, status, message}`（无 response_model） |
| `POST /catch-up` | 174 | admin | 未用；幂等（已追平返回 `generated_count=0`）；逐日 checkpoint；失败附 `failed_date`/`error` |
| `POST /generate-next` | 201 | admin | 未用 |
| `GET /validation` | 237 | admin | 已用 |
| `GET /portfolios/{code}/status` | 261 | **user** | 已用；**`missing_dates = []` 恒空（:296，注释"简化"）**；含 `negative_cash_platforms`（#71） |
| `DELETE /{code}/{date}` | 320 | admin | 已用（仅"删除最新"一个入口） |
| `DELETE /{code}/bulk/{from_date}` | 365 | admin | 未用；`dry_run=true` 纯预览；无 `confirm=true` 报 422 `CONFIRM_REQUIRED`；逐日 commit 倒序删除 |

- `PortfolioValueSnapshot` 字段（models/portfolio_value_snapshot.py）：`snapshot_date / total_value(Numeric 15,4) / total_shares(15,2) / unit_price(10,4) / frozen_shares / unit_price_change_pct(8,4，可空) / in_transit_total(15,4，默认0) / created_at`，唯一约束 `(portfolio_code, snapshot_date)`；ORM 层禁 update/delete（`_delete_existing_snapshots` 走 bulk 绕过）。**注意：表里虽存了 `unit_price_change_pct`，决策⑤明确涨跌由前端按相邻行算，list 响应不带该字段。**
- 集合差模式可直接复用的先例：`market_data_service.py::get_nav_coverage`（:86-141）——`TradingCalendar.calendar_date` 过滤 `is_open.is_(True)` 减已同步日期集，`sorted(差集)`；`start > end` 抛 `BusinessError("INVALID_DATE_RANGE", ..., http_status=422)`（:104-109）。
- `snapshot_service.py` 公共函数面：generate_daily_snapshots / recalculate_snapshots / catch_up_snapshots / generate_next_snapshot / validate_snapshot_dependencies。**当前无任何读侧查询函数**，本计划新增的两个函数放 `generate_next_snapshot`（:504）之后。
- 路由顺序无冲突：GET 只有 `/validation` 与 `/portfolios/{code}/status`，新增 `/portfolios/{code}/list` 放 status 端点之后即可。
- 测试基建：`tests/factories.py` 有 `create_portfolio / create_value_snapshot(db, code, date, total_value=, total_shares=, unit_price=) / create_position_snapshot / ensure_trading_day`；conftest 交易日历 2025-01-01~2026-12-31 **工作日=交易日**；fixture 惯例 `client, admin_headers / viewer_headers, test_db`。

### CLI 契约（关键结论：**无契约漂移**）

- `ir-cli/scripts/gen_response_fields.py` 只处理 `COMMAND_SCHEMA_MAP` 白名单（含 `("snapshot","status","SnapshotStatusResponse")`，:41）。`SnapshotStatusResponse` 字段不变（`missing_dates` 早已声明）→ `response_fields.py` 零 diff；新 list schema 不在白名单 → 不影响。
- 但 `backend/openapi.json` 是**提交在仓库的**派生文件，新增端点后须重导提交（需运行中的后端：`cd backend && uvicorn app.main:app` 另开终端 `python export_openapi.py`）。
- `ir portfolio context` 会原样输出 status JSON（commands/portfolios.py:90）——`missing_dates` 变真实值是行为改善，无需改代码。
- **不加 `ir snapshot list` 命令**（issue 未要求，控范围）。

### 前端现状

- `app/portfolio/[code]/snapshots/page.tsx` 538 行单文件：无 AdminGuard；"快速更新" `handleQuickUpdate`（:70-86）错用 `generate(今天)`；重算对话框含死 force checkbox（:462-473，原生 `<input type="checkbox">`）；标题 `text-3xl font-bold`（:162）、统计值 `text-2xl font-bold`（:178 等）违规；`unit_price?.toFixed(4)` 内联格式化（hooks/useSnapshot.ts:30）。
- `frontend/src/app/m/portfolio/[code]/` 下**无 snapshots/**；移动端组合详情 `manageLinks`（m/portfolio/[code]/page.tsx:101-105）注释明确"快照管理暂无移动端路由"。
- 既有可复用件：`AdminGuard`（components/shared/AdminGuard.tsx，viewer 显示 EmptyState「无权限访问」）；壳页先例——桌面 `app/products/page.tsx`（MainLayout + AdminGuard + Content），移动 `app/m/products/page.tsx`（无 MainLayout，`m/layout.tsx` 统一供 MobileLayout）；共享内容件 props 先例 `{ basePath: string; variant?: "desktop" | "mobile" }`，组件内 `useParams()` 自取 code（SubscriptionsContent.tsx:71-108）。
- `ui/` 现有：date-picker（`showTradingDays` 交易日标注）、date-range-picker、pagination、alert-dialog 等；**无 checkbox**。package.json 无 `@radix-ui/react-checkbox`（需新增依赖，见 §4.1）。
- 移动端表格先例：同一 `ui/table` 外层套 `overflow-x-auto`（TradesContent.tsx:106 注释）。
- 格式化工具（lib/utils.ts）：`formatNav`(4位) / `formatShares`(2位) / `formatCurrency` / `getNumberCellClass()`("text-right font-mono tabular-nums") / `getSignedReturn(pct百分数)→{text,colorClass}` / `getStatusBadgeVariant`（running→warning、success→success、failed→destructive，直接适配 sync-job 状态）。
- 轮询先例仅 useNotification.ts（静态 60s）；sync-job 需用 react-query v5 函数式 `refetchInterval`（终态停轮询）。
- 危险确认按钮先例：`AlertDialogAction className="bg-destructive text-white hover:bg-destructive/90"`（ClosePortfolioDialog.tsx:87；button.tsx destructive variant 同款）。SubscriptionsContent/TradesContent 的 `text-destructive-foreground` 属并存存量，本页按 issue 统一 `text-white`。
- 规范条文：标题 `text-2xl font-semibold`（§5）；表格 §8（数字列右对齐 number-cell、表头 text-muted-foreground 常规字重、无斑马纹、空态/加载态形态）；后台任务进度 §14（Badge+Loader2 行内区块，不引 Progress）；dry_run 两段式 §14（文案模板「将删除 X 张快照（YYYY-MM-DD ~ YYYY-MM-DD），此操作不可恢复」）；筛选场景不标交易日、**录入/操作场景 DatePicker 仍 `showTradingDays`**（§10 边界）。

---

## 1. 改动地图

| 层 | 文件 | 动作 |
|---|---|---|
| backend | `app/schemas/snapshot.py` | +`SnapshotListItem` / `SnapshotListResponse` |
| backend | `app/services/snapshot_service.py` | +`list_portfolio_snapshots()` / +`compute_missing_snapshot_dates()` |
| backend | `app/routers/snapshots.py` | +`GET /portfolios/{code}/list`；status 的 `missing_dates` 接真实计算 |
| backend | `openapi.json` | 重导（新增 1 端点 + 2 schema） |
| backend | `tests/integration/test_snapshot_list.py` | **新建**（list + missing_dates 用例） |
| frontend | `package.json` / lock | +`@radix-ui/react-checkbox`（新依赖，PR 部署影响注明） |
| frontend | `src/components/ui/checkbox.tsx` | **新建** shadcn 基件 |
| frontend | `src/types/snapshot.ts` | +list/catchUp/generateNext/async/bulk 类型 |
| frontend | `src/types/syncJob.ts` | **新建** `SyncJob` |
| frontend | `src/lib/api/snapshot.ts` | +list/generateNext/catchUp/recalculateAsync/deleteBulk；`recalculate` 删 `force` |
| frontend | `src/lib/api/syncJob.ts` | **新建** `syncJobApi.get` |
| frontend | `src/lib/api/index.ts` | 注册 syncJobApi + 新类型导出 |
| frontend | `src/hooks/useSnapshot.ts` | +5 hook（list/generateNext/catchUp/recalculateAsync/bulkDelete），删 `useRecalculateSnapshots`，`useGenerateSnapshot` toast 去 toFixed |
| frontend | `src/hooks/useSyncJob.ts` | **新建** 2s 条件轮询 |
| frontend | `src/components/shared/SnapshotsContent.tsx` | **新建**（页面主体） |
| frontend | `app/portfolio/[code]/snapshots/page.tsx` | 精简为壳 |
| frontend | `app/m/portfolio/[code]/snapshots/page.tsx` | **新建**移动壳 |
| frontend | `app/m/portfolio/[code]/page.tsx` | manageLinks +「快照管理」入口，更新注释 |

无 DB 迁移；ir-cli 代码零改动。

## 2. 阶段划分

| 阶段 | 内容 | 产出验证 |
|---|---|---|
| 1 | 后端：schemas + service 两函数 + list 端点 + status missing_dates + pytest | `pytest tests/integration/test_snapshot_list.py` 全绿 + 全量回归 |
| 2 | 契约：openapi.json 重导 + `gen_response_fields.py --check` | --check 通过（预期零 diff） |
| 3 | 前端基件与数据层：checkbox（先 `npm i @radix-ui/react-checkbox`）+ types + api + hooks | `npx tsc --noEmit` 过 |
| 4 | SnapshotsContent + 双端壳 + 移动入口 | `npm run lint && npm run build` 0 error + 人工验收矩阵 |
| 5 | 全量验证 + PR | 后端 pytest 全量、前端 lint/build、CLI 契约 CI 绿 |

阶段 1→2→3→4 严格顺序。

---

## 3. 后端改动明细（阶段 1-2）

### 3.1 `app/schemas/snapshot.py` 追加

```python
class SnapshotListItem(BaseModel):
    """快照历史列表项（#146）。涨跌不由后端给——前端按相邻行 unit_price 推导。"""
    snapshot_date: date
    unit_price: float
    total_shares: float
    total_value: float
    in_transit_total: float


class SnapshotListResponse(BaseModel):
    """快照历史列表响应。total = 过滤后全量计数（limit 截断前），防无声截断。"""
    portfolio_code: str
    items: List[SnapshotListItem]
    total: int
    limit: int
```

（DB 四列均非空 → 全部非 Optional；序列化沿既有 float 先例，与 `SnapshotGenerationResult.unit_price: Optional[float]` 同款。）

### 3.2 `app/services/snapshot_service.py` 新增两公共函数

放 `generate_next_snapshot`（:504-553）之后、`validate_snapshot_dependencies` 之前。

```python
def list_portfolio_snapshots(
    db: Session,
    portfolio_code: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    """快照历史列表：snapshot_date 倒序，可选闭区间过滤（#146）。

    start_date > end_date → BusinessError INVALID_DATE_RANGE(422)
    （与 market_data_service.get_nav_coverage 同模式）。
    返回 {"items": [PortfolioValueSnapshot...], "total": int}，
    total 为 limit 截断前的过滤后计数（total > len(items) 即被截断）。
    不 commit、不抛 HTTPException（分层约定 §4.1）。
    """
```

实现要点：`INVALID_DATE_RANGE` 校验 → `db.query(PortfolioValueSnapshot).filter(portfolio_code==...)` 按需叠加 `snapshot_date >= / <=` → `total = query.count()` → `query.order_by(snapshot_date.desc()).limit(limit).all()`。

```python
def compute_missing_snapshot_dates(
    db: Session,
    portfolio_code: str,
    first_date: date,
    last_date: date,
) -> List[date]:
    """首末快照日闭区间内 is_open=true 但无快照的交易日（升序）（#146）。

    集合差模式同 get_nav_coverage：trading_calendar 区间交易日集 − 区间快照日期集。
    语义边界：只统计 [first, last] 区间内部空洞；最新快照日之后尚未生成的日子
    不算 missing（属 catch-up 语义），首日之前同理。
    """
```

### 3.3 `app/routers/snapshots.py`

**新增端点**（放 status 端点 :261 之后、DELETE :320 之前）：

```python
@router.get("/portfolios/{code}/list", response_model=SnapshotListResponse)
def list_snapshots(
    code: str,
    start_date: Optional[date] = Query(None, description="起始日期(含) YYYY-MM-DD"),
    end_date: Optional[date] = Query(None, description="结束日期(含) YYYY-MM-DD"),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_user),
):
    """快照历史列表（#146）。权限与 status 一致：所有登录用户。"""
```

- 组合存在性 404 复制 status 的写法（`PORTFOLIO_NOT_FOUND`，:273-278）。
- 调 `list_portfolio_snapshots` → items 逐条 `SnapshotListItem.model_validate(row)`（或显式字段构造，Numeric→float 由 Pydantic  coercion）→ 包 `SnapshotListResponse(portfolio_code=code, items=..., total=..., limit=limit)`。
- import 区补两个 schema 与 service 函数。

**status 的 missing_dates 落地**（:295-296 两行替换）：

```python
    # 首末快照日区间内缺失的交易日（#146）：区间无快照（无基线）时为空
    missing_dates: List[str] = []
    if latest and earliest:
        missing_dates = [
            d.isoformat()
            for d in compute_missing_snapshot_dates(
                db, code, earliest.snapshot_date, latest.snapshot_date
            )
        ]
```

（删掉"简化"注释。单快照时 first==last，区间一天且有快照 → 自然为空，无需特判。）

### 3.4 后端测试（`tests/integration/test_snapshot_list.py` 新建）

数据基础：conftest 日历工作日=交易日。建议用 2025-06-02(一)~06-06(五) 连续 5 个交易日 + 06-07/08 周末。造数用 `create_portfolio(db, code=..., status="active")` + `create_value_snapshot(...)`（只需市值表，list/status 不读另两表）。

`class TestSnapshotList`：

| 用例 | 断言 |
|---|---|
| `test_list_desc_order` | 造 3 日快照 → items 按 snapshot_date 倒序、字段齐全（含 in_transit_total）、total=3、limit=500 |
| `test_list_date_range_filter_closed` | start/end 闭区间：边界日**包含**，区间外剔除 |
| `test_list_limit_truncation_total_kept` | 3 快照 + `limit=2` → items=2（最新两日）、**total=3**（防无声截断，决策①） |
| `test_list_empty` | 无快照组合 → items=[]、total=0 |
| `test_list_portfolio_not_found` | 404 `PORTFOLIO_NOT_FOUND` |
| `test_list_inverted_range_422` | start>end → 422 `INVALID_DATE_RANGE` |
| `test_list_viewer_allowed` | `viewer_headers` 200（权限与 status 一致，决策①） |

`class TestSnapshotStatusMissingDates`：

| 用例 | 断言 |
|---|---|
| `test_missing_dates_real_holes` | 周一~周五只造一/二/五 → status.missing_dates == [周三, 周四]（ISO 升序） |
| `test_missing_dates_weekend_not_counted` | 连续一~五全有 → []（周末本就不是交易日，天然不入选） |
| `test_missing_dates_continuous_empty` | 全连续 → [] |
| `test_missing_dates_no_snapshots` | 无快照 → [] 且 latest/first 为 null（不炸） |
| `test_missing_dates_after_latest_not_counted` | 最新快照日后尚有未生成交易日 → 不计入 missing（区间语义边界） |

### 3.5 契约（阶段 2）

1. 启动本地后端 → `cd backend && python export_openapi.py` → diff 自查：仅多 1 路径 + 2 schema。
2. `python ir-cli/scripts/gen_response_fields.py --check` → 预期 `[ok]` 零 diff（§0 CLI 结论）；若意外失败，先查 openapi.json 是否混入本地版本杂波，**不要提交陌生 diff**。

---

## 4. 前端改动明细（阶段 3-4）

### 4.1 基件 `ui/checkbox.tsx`（新建）

先 `npm install @radix-ui/react-checkbox`（**新依赖**，package.json + lock 进 diff，PR 部署影响注明）。实现取 shadcn 官方原样（forwardRef 写法对齐仓内其他 ui 件风格）：

```tsx
"use client"
import * as React from "react"
import * as CheckboxPrimitive from "@radix-ui/react-checkbox"
import { Check } from "lucide-react"
import { cn } from "@/lib/utils"
// Root: "h-4 w-4 shrink-0 rounded-sm border border-primary shadow
//   focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring
//   disabled:cursor-not-allowed disabled:opacity-50
//   data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
```

规格依据规范 §13 登记（rounded-sm、选中 bg-primary）。

**checkbox 用在哪**（决策④移除 force checkbox 后的真实使用点，本计划定死）：两个破坏性对话框的**风险确认勾选**，勾选前确认按钮 disabled——
① 区间重算对话框：「我已了解重算将删除区间内全部快照并重新生成，此操作不可撤销」；
② 批量删除确认步（dry_run 预览后）：「我已了解将删除上述快照并级联回退，此操作不可恢复」。
替换掉原页面唯一的原生 checkbox，满足 issue 违规收敛要求。

### 4.2 types

`types/syncJob.ts`（新建，对齐后端 `SyncJobResponse`）：

```ts
export interface SyncJob {
  id: number;
  job_type: string;
  status: string;            // pending | running | success | failed
  params?: Record<string, unknown> | null;
  total: number; done: number;
  success_count: number; failed_count: number; skipped_count: number;
  error_message?: string | null;
  triggered_by: string;
  created_at?: string | null; started_at?: string | null; finished_at?: string | null;
}
```

`types/snapshot.ts` 追加：

```ts
export interface SnapshotListItem {
  snapshot_date: string; unit_price: number; total_shares: number;
  total_value: number; in_transit_total: number;
}
export interface SnapshotListResponse {
  portfolio_code: string; items: SnapshotListItem[]; total: number; limit: number;
}
export interface SnapshotCatchUpResult {
  portfolio_code: string; to_date: string; generated_count: number;
  generated_dates: string[]; latest_snapshot_date?: string | null;
  message?: string | null; failed_date?: string | null; error?: string | null;
}
export interface SnapshotGenerateNextResult { /* 同后端 SnapshotGenerateNextResult：success/message/portfolio_code/generated_date/total_value?/total_shares?/unit_price?/warnings? */ }
export interface RecalculateAsyncSubmitResult { job_id: number; status: string; message: string; }
export interface BulkDeleteDryRunResult { dry_run: true; portfolio_code: string; from_date: string; count: number; snapshot_dates: string[]; }
export interface BulkDeleteResult {
  success: boolean; message: string; deleted_count: number;
  details?: Array<{ snapshot_date: string; deleted: number; cascaded_subs: number; cascaded_events: number }>;
}
```

### 4.3 api 层

`lib/api/snapshot.ts`：

```ts
list: (portfolioCode: string, params?: { start_date?: string; end_date?: string; limit?: number }) =>
  request<SnapshotListResponse>({ method: "GET", url: `/snapshots/portfolios/${portfolioCode}/list`, params }),
generateNext: (portfolioCode: string) => /* POST /snapshots/generate-next {portfolio_code} */,
catchUp: (portfolioCode: string, toDate: string) => /* POST /snapshots/catch-up */,
recalculateAsync: (portfolioCode: string, startDate: string, endDate: string) =>
  /* POST /snapshots/recalculate-async → RecalculateAsyncSubmitResult */,
deleteBulk: (portfolioCode: string, fromDate: string, mode: "dry_run" | "confirm") =>
  /* DELETE /snapshots/{code}/bulk/{fromDate}，params: mode==="dry_run" ? {dry_run:true} : {confirm:true}，
     返回类型 BulkDeleteDryRunResult | BulkDeleteResult（调用方按 mode 收窄） */,
```

`recalculate`：**保留函数、删 `force` 形参与 body 字段**（issue 待实现改动原文要求；同步端点保留，CLI 仍可用）。

`lib/api/syncJob.ts`（新建）：`syncJobApi.get(jobId: number) → GET /sync-jobs/${jobId} → SyncJob`。
`lib/api/index.ts`：`export { syncJobApi } from "./syncJob";` + 按需导出新类型。

### 4.4 hooks

`hooks/useSyncJob.ts`（新建）：

```ts
export function useSyncJob(jobId: number | null) {
  return useQuery({
    queryKey: ["sync-jobs", jobId],
    queryFn: () => syncJobApi.get(jobId!),
    enabled: jobId != null,
    // 函数式 refetchInterval：仅 pending/running 轮询，终态（含查询失败/无数据）停止
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "pending" || s === "running" ? 2000 : false;
    },
  });
}
```

`hooks/useSnapshot.ts`：

| hook | 要点 |
|---|---|
| `useSnapshotList(portfolioCode)` | queryKey `["snapshots","list",portfolioCode]`；status 同款 invalidation 覆盖（`["snapshots"]` 前缀失效即同时刷 status+list） |
| `useGenerateNextSnapshot()` | onSuccess toast「快照生成成功」`已生成 {generated_date}，净值 {formatNav(unit_price)}`；invalidate `["snapshots"]`+`["portfolios"]`；onError toast 透传（NO_SNAPSHOT_BASELINE / CALENDAR_NOT_SYNCED 等 message 直接可见） |
| `useCatchUpSnapshots()` | onSuccess：`failed_date` 存在 → **warning** toast `追平中断于 {failed_date}，已生成 {generated_count} 日：{error}`；否则 success toast `{message}`；invalidate 同上 |
| `useRecalculateAsync()` | mutationFn 调 `recalculateAsync`；**onSuccess 只返回数据不 toast 终态**——由组件接 `job_id` 置 `activeJobId`；onError toast（409 RECALC_JOB_CONFLICT 的 message「已有快照重算任务在运行中」直接展示） |
| `useBulkDeleteSnapshots()` | mutationFn `{portfolioCode, fromDate, mode}` 透传 api.deleteBulk；**toast 由组件按 mode 分别处理**（dry_run 不 toast，confirm 成功 toast `message`），hook 内只做 confirm 成功后的 invalidate `["snapshots"]`+`["portfolios"]` |
| `useGenerateSnapshot` 既有 | toast message 的 `unit_price?.toFixed(4)` → `formatNav(unit_price)`（违规收敛） |
| `useRecalculateSnapshots` 既有 | **删除**（被 async 流程替代，同步能力仍经 CLI 可用）；`useValidateSnapshot` / `useDeleteSnapshot` 保留不动 |

### 4.5 `components/shared/SnapshotsContent.tsx`（新建，页面主体）

签名对齐既有共享件：

```tsx
interface SnapshotsContentProps {
  basePath: string;                        // "/portfolio" | "/m/portfolio"
  variant?: "desktop" | "mobile";          // 默认 desktop
}
export default function SnapshotsContent({ basePath, variant = "desktop" }: SnapshotsContentProps)
// 组件内 useParams() 取 code（SubscriptionsContent 先例）
```

内部状态：

```ts
const [activeJobId, setActiveJobId] = useState<number | null>(null);   // 重算任务跟踪
const [catchUpOpen, setCatchUpOpen] = useState(false);   // + toDate
const [singleOpen, setSingleOpen] = useState(false);     // + singleDate + validationResult（预检两段，逻辑搬自现页 :88-115）
const [recalcOpen, setRecalcOpen] = useState(false);     // + startDate/endDate + recalcAck(checkbox)
const [bulkOpen, setBulkOpen] = useState(false);         // + bulkFromDate + bulkPreview(BulkDeleteDryRunResult|null) + bulkAck
const [pendingDeleteDate, setPendingDeleteDate] = useState<string | null>(null);
```

区块结构（自上而下）：

1. **Header**：返回 ghost（`Link ${basePath}/${code}` + ArrowLeft）+ `<h1 className="text-2xl font-semibold">快照管理</h1>`（**双端统一**，规范 §5）+ 副标题 `text-sm text-muted-foreground`「管理组合历史快照数据，支持手动生成、追平与区间重算」。
2. **状态概览 Card**：三格统计——最新快照日期 / 快照总数 / 最早快照日期；label `text-xs text-muted-foreground`，值 **`text-lg font-semibold`**（18px 分区标题档；日期/计数非金额，不用 amount-large——issue 违规项的落点）。`negative_cash_platforms` 非空 → 既有 destructive Alert 原样保留。`missing_dates` 非空 → 既有 Badge 区块保留（此时终于有真实数据）。
3. **操作区 Card**：`flex flex-wrap gap-2`（移动端 `grid grid-cols-2`）按钮行，层级按规范 §14：
   - 「生成下一日快照」**default 主操作**，一键直发（非破坏性无需确认），pending 时按钮内 Loader2 +「生成中…」；替代旧"快速更新"。
   - 「追平至日期」outline → 对话框：`DatePicker showTradingDays` + 说明 Alert（逐日生成、失败日前成果保留）+ 确认（Loader2）。
   - 「单日生成」outline → **现有预检两段对话框逻辑整体搬迁**（validation checks 渲染 :350-386 保留，字号/色 token 顺手合规）。
   - 「区间重算」outline → 对话框：start/end 两个 `DatePicker showTradingDays` + 文案改为异步语义（「提交后台任务执行，页面内展示进度与终态；任一日失败整体回滚无变化」）+ 风险 Alert + **ui/checkbox 风险确认** + 「提交重算任务」solid `bg-destructive text-white hover:bg-destructive/90`，disabled = 日期未齐 || start>end || !ack || isPending。**force checkbox 删除。**
   - 「批量删除」outline + Trash2 图标（危险入口但非确认动作，不用 solid）→ 两段式对话框（下述）。
4. **重算任务进度区块**（`activeJobId` 非空时渲染，规范 §14 行内区块，不引 Progress）：Alert/Card 行内 = 状态 `Badge variant={getStatusBadgeVariant(job.status)}` + 进行中 `Loader2 animate-spin` + 文案「区间重算 {start} ~ {end}」（从 `job.params` 取）+ failed 时 `error_message` 全文 `text-sm` 展示 + 终态后右侧 X 关闭（`setActiveJobId(null)`）。终态副作用用 `useEffect` 监听 `job?.status`：success → toast「重算完成，共处理 N 个交易日」+ invalidate `["snapshots"]`/`["portfolios"]`；failed → error toast「重算失败已整体回滚」+ 区块内展示 error_message。注意 effect 去重（对同一 job 终态只触发一次，`useRef` 记录已处理 jobId+status）。
5. **历史快照表格 Card**：
   - 数据 `useSnapshotList(code)`；首载 LoadingState（表体居中 Loader2，规范 §8）；空 → EmptyState「暂无快照」；`total > items.length` → 表下 `text-xs text-muted-foreground`「仅显示最近 {items.length} 条，共 {total} 条」。
   - 列：**日期 / 净值 / 涨跌 / 份额 / 市值 / 在途 / 操作**。数值列头与单元格右对齐 `getNumberCellClass()`；日期左对齐；操作列右对齐。
   - 格式化：净值 `formatNav`、份额 `formatShares`、市值/在途 `formatCurrency`（在途 0 也照常显示 `¥0.00`，不做特殊折叠）。
   - **涨跌列（决策⑤）**：`items[i]` 涨跌 = `(items[i].unit_price / items[i+1].unit_price − 1) × 100`（数组倒序，i+1 即前一交易日；快照连续原则保证相邻行=相邻交易日）；末行无前值 → `--`。渲染 `getSignedReturn(pct)` → `<span className={colorClass}>{text}</span>`（红涨绿跌走 token，§1.1）。**注意 `getSignedReturn` 入参是百分数数值（5.23 表 5.23%），不是小数**。
   - **删除操作列**：仅 `items[0]`（最新日）行渲染可用 `ghost` Trash2 按钮；其余行同按钮 `disabled` + `title="快照连续原则：仅可删除最新日快照"`。点击 → AlertDialog（沿用现页 :514-534，描述含级联回退提示），确认按钮 `className="bg-destructive text-white hover:bg-destructive/90"`。
   - 移动端：表格外层 `overflow-x-auto`（TradesContent 先例），列不裁剪。
6. **批量删除两段式对话框**（规范 §14 模板）：
   - 第一步：`DatePicker showTradingDays` 选起始日 +「预览影响」→ `deleteBulk(mode:"dry_run")`；
   - 第二步（拿到 preview）：文案「将删除 {count} 张快照（{最早} ~ {最晚}），此操作不可恢复」（日期取 `snapshot_dates` 首末——返回是倒序，注意取头尾）+ 日期列表（`max-h-40 overflow-y-auto` 全量列出）+ ui/checkbox 风险确认 +「确认删除」solid destructive（disabled = !ack || isPending）→ `deleteBulk(mode:"confirm")` → 成功 toast 后关框、清 preview。
   - `count === 0` → 展示「该日期及之后无快照可删除」，不出确认区。**拿不到预览结果时确认按钮不出现**（规范硬性）。
   - 重复提交防护：confirm pending 期间全框按钮 disabled。

### 4.6 壳页与移动入口

- `app/portfolio/[code]/snapshots/page.tsx` **整体替换**为（products 先例）：

```tsx
"use client";
import MainLayout from "@/components/layout/MainLayout";
import AdminGuard from "@/components/shared/AdminGuard";
import SnapshotsContent from "@/components/shared/SnapshotsContent";

export default function PortfolioSnapshotsPage() {
  return (
    <MainLayout>
      <AdminGuard>
        <SnapshotsContent basePath="/portfolio" variant="desktop" />
      </AdminGuard>
    </MainLayout>
  );
}
```

- `app/m/portfolio/[code]/snapshots/page.tsx` **新建**（m/products 先例，无 MainLayout）：

```tsx
"use client";
import AdminGuard from "@/components/shared/AdminGuard";
import SnapshotsContent from "@/components/shared/SnapshotsContent";

export default function MobilePortfolioSnapshotsPage() {
  return (
    <AdminGuard>
      <SnapshotsContent basePath="/m/portfolio" variant="mobile" />
    </AdminGuard>
  );
}
```

- `app/m/portfolio/[code]/page.tsx`：`manageLinks`（:101-105）末尾加 `{ label: "快照管理", href: \`/m/portfolio/${code}/snapshots\` }`，并把 :99-100 注释改为「份额变动暂无移动端路由，不在列表展示」。

---

## 5. 测试方案

### 后端（阶段 1 内）

- 新文件 `test_snapshot_list.py` 两类 12 用例（§3.4 表）；
- 回归：`cd backend && .venv/bin/python -m pytest tests/ -q` 全量（重点：test_snapshots.py / test_snapshot_catchup.py / test_snapshot_recalc_async.py 不受 missing_dates 真值化影响——status 断言若写有 `missing_dates == []` 需按真值修正，实施时 grep 确认）。

### 契约（阶段 2 内）

- `python ir-cli/scripts/gen_response_fields.py --check`；openapi.json diff 人工核对。

### 前端（阶段 3-5）

- 无单测框架，不新增 E2E；`npm run lint && npm run build` 0 error；
- **人工验收矩阵**（对照 issue 验收断言）：

| # | issue 断言 | 验证操作 |
|---|---|---|
| 1 | 逐日历史表格（日期/净值/涨跌/份额/市值/在途）与 DB 一致 | 页面表格 vs `ir snapshot status` / DB 抽查 3 日行；涨跌抽查 = 当日净值/前一日净值−1 |
| 2 | 「生成下一日快照」成功；「追平至日期」一次补多日 | 各点一次；生成后表格顶部出现新行；追平 3 日 → toast「共生成 3 日」 |
| 3 | 区间重算走异步：页面内进度与终态；重复提交被拒 | 提交区间重算 → 进度区块 Badge running → 终态 success/failed + 失败时 error_message 可见；运行中再提交 → toast「已有快照重算任务在运行中」；**HTTP 不再长时间阻塞**（提交即时返回） |
| 4 | 批量删除 dry_run→confirm；单日删除仅最新日可点 | 批量：预览文案「将删除 X 张快照（起 ~ 止）」与列表正确，确认后表格缩短；表格内非最新日删除按钮 disabled |
| 5 | 非管理员无权限提示；移动端可访问且功能一致 | viewer 登录双端 URL → EmptyState「无权限访问」；admin 移动 `/m/portfolio/{code}/snapshots` 全操作走一遍；移动端组合详情页尾出现「快照管理」入口 |
| 6 | 无 visual-spec 违规 | 全页无 text-3xl/text-2xl font-bold 统计值；确认按钮 solid `bg-destructive text-white`；数值列 number-cell 右对齐；无原生 checkbox、无内联 toFixed |
| 7 | missing_dates 真实返回 | 人为制造空洞（删中间一日快照不可用——改用测试环境造数或直接 `ir snapshot status` 对比交易日历）；页面「缺失的快照日期」区块渲染 |
| 8 | limit 截断可见（决策①附加） | 快照数 > limit 时（或临时 `?limit=2` 直调 API）表格下方「仅显示最近 N 条，共 M 条」 |

---

## 6. 验收自查清单（实施完成前逐项过）

- [ ] `GET /api/snapshots/portfolios/{code}/list`：倒序/闭区间过滤/limit+total/404/422/viewer 200，openapi.json 已重导
- [ ] status `missing_dates` 返回真实空洞（区间语义：仅限首末快照日之内）
- [ ] `gen_response_fields.py --check` 零 diff；ir-cli 代码未动
- [ ] 页面五操作全部可用：generate-next / catch-up / generate(预检) / recalculate-async(进度+终态) / 删除(单日+bulk两段式)
- [ ] 「快速更新」与 force checkbox 彻底移除，页面无 generate(今天) 调用
- [ ] 历史表格六列 + 涨跌相邻行计算 + 末行 `--` + 单行删除仅最新日
- [ ] AdminGuard 双端；移动壳页 + 组合详情入口；移动端表格 overflow-x-auto
- [ ] ui/checkbox 落地并用于两处风险确认；`@radix-ui/react-checkbox` 进 package.json 并在 PR 部署影响注明
- [ ] 字号/危险按钮/数字格式化合规（断言 6）；`useSnapshot` toast 无 toFixed
- [ ] `useRecalculateSnapshots` 已删、`snapshotApi.recalculate` 已无 force
- [ ] 后端 pytest 全绿、前端 lint/build 0 error、CI 全绿

## 7. 风险与备注

1. **基线分支**：本计划撰写时 #125/#126 在 `feature/125-sub-trade-filters` 未合 dev。实施前先 `git fetch`：若已合则自 dev 切 `feature/146-snapshots-refactor`；若未合，以该分支为基线或等其合并（SnapshotsContent 不依赖筛选基件，改动文件不相交，冲突风险低）。
2. **老 status 测试可能断言空 missing_dates**：`missing_dates` 真值化是行为变更，实施时 `grep -rn "missing_dates" backend/tests/` 全量排查修正；`ir portfolio context` 输出随之带真值（改善，PR 描述注明）。
3. **快照连续性保证涨跌口径**：相邻行=相邻交易日由「快照连续原则」保证（§2.1），但 limit/区间过滤截断的是**尾部旧数据**、不影响剩余行相邻性——除响应窗口末行（最旧行）恒 `--` 外无需特判。若未来快照允许空洞，前端涨跌口径要重议（届时可改用表内 `unit_price_change_pct` 字段，本计划不预先输出该字段，YAGNI）。
4. **重算进度区块的终态 effect 去重**：`useEffect` 依赖 `job?.status`，success/failed  toast + invalidate 必须每 job 只触发一次（ref + 记录 `${jobId}:${status}`），否则轮询最后一次与停轮询后的重渲染可能双 toast。
5. **`refetchInterval` 函数式写法**需 react-query v5（仓内 ^5.62，支持）；勿用布尔静态值，否则终态后无限轮询。
6. **单日删除入口从状态卡搬到表格行**：状态卡不再放「删除最新快照」按钮（操作收口到表格，避免双入口漂移）；删除的 AlertDialog 文案保留级联回退提示。
7. **catch-up 逐日 commit 语义**（单日失败前功保留）与 recalculate 单事务语义（失败全回滚）不同，两个对话框的说明文案必须如实区分，勿复用同一句。
8. **新依赖唯一性**：本 PR 只引入 `@radix-ui/react-checkbox` 一个依赖，不得夹带其他。
9. **PR 描述**：改动含「同步 recalculate 前端入口移除」（CLI `ir snapshot recalculate` 不受影响）与「status.missing_dates 行为变更」两条部署影响须写明。
