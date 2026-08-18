# 实施计划：#173~#176 调仓交易页四联改动（手续费录入 / 列表拆列 / pending 编辑 / 按钮矩阵 + product_name 读侧派生）

> 目标：一次性落地四个 issue——#173 表单补手续费录入 + 列表拆「金额/份额/手续费」三列；#174 pending 交易编辑 Dialog；#175 交易列表 `product_name` 后端读侧派生（根治分页上限导致名称回退）；#176 操作按钮对齐后端允许矩阵。
>
> **分支/PR 策略（用户已定）**：单分支 `feature/173-176-trades-ux`，4 个逻辑独立 commit，单个 PR（描述含 `fixes #173`、`fixes #174`、`fixes #175`、`fixes #176`）。理由：#173/#174/#176 集中改 `TradesContent.tsx` 同一批代码块（renderMainRow 操作列、表头、Dialog 区），#175 亦改该文件 `getProductName`/`useProductList`；串行多 PR 必然反复冲突 rebase。
>
> **前置状态（已核实，行号以 dev 分支当前代码为准）**：
>
> - 后端 `PUT /api/trades/{id}` 已支持 pending 修改（`routers/trades.py:231-294`），仅拦 confirmed（`CANNOT_MODIFY_CONFIRMED`）；改 `trade_date` 自动联动重算 `confirm_date`；金额类字段变动自动同步配对 CASH 腿（`paired.amount = actual_amount or amount`）。
> - 后端 cancel 仅 pending+非场内（`trade_service.py` `cancel_trade`，场内抛 `CANNOT_CANCEL_EXCHANGE`）；delete 仅拦 confirmed（`CANNOT_DELETE_CONFIRMED`），pending 可删且级联删配对腿。
> - 前端 `useUpdateTrade` hook（`useTrade.ts:85-108`）与 `TradeUpdate` 类型（`types/trade.ts:44-52`）已就绪；`useDeleteTrade` 目前**无 toast**（已批准本次补）。
> - positions API 读侧派生先例：`routers/positions.py:105`（批量查 Product 建 name_map，`model_validate().model_dump()` 后挂 `row["product_name"]`，防 N+1），`schemas/position.py:41-42` 字段注释模式。
> - `GET /api/trades` 当前**无 response_model**（openapi 中响应 schema 为 `{}`）；ir-cli 契约由 `gen_response_fields.py` 从 `components.schemas.TradeResponse` 抽取（`("trade","list","TradeResponse","list","trade")`）。
> - 移动端交易页 `app/m/portfolio/[code]/trades/page.tsx` 为薄壳，复用 `TradesContent variant="mobile"`——单文件改动天然覆盖双端。
> - 按钮 tooltip 的文件内既有约定为原生 `title` 属性（`TradesContent.tsx:438/442/449`），不引入 ui/tooltip。

---

## 0. 评审结论摘要

四个 issue 根因分析均准确（已逐行对照源码核实），选定方案全部采纳，无方案级异议。评审补充如下，已并入计划：

| Issue | 结论 | 评审补充 |
|---|---|---|
| #173 | 方案 A 采纳 | ① 买入行「金额」列口径经用户确认为 **`trade.amount`（净额）**，手续费单列，买入行 金额+手续费=实际扣款、卖出行 金额−手续费=实际到账，买卖对称。② pending 卖出行创建时 `amount = 0 + fee`、`actual_amount = 0`（确认时才回填 shares×nav），金额列沿用 truthy 判断（`0`/null → `-`），避免把 fee 误显为成交金额。③ fee 非 0 才显示金额、否则 `-`（场外 0 手续费占多数，列更干净）。 |
| #174 | 方案 A 采纳 | 已知边界（后端既有语义，**不属本 PR**）：PUT 不做可用现金/份额校验（确认时才校验 `INSUFFICIENT_CASH/SHARES`）、不校验交易日；编辑买入 amount 时配对 CASH 腿按 `actual_amount or amount` 同步。编辑表单不含产品/平台/方向（后端不支持改），Dialog 内只读展示。 |
| #175 | 方案 B 采纳 | ① 与 positions 读侧派生模式完全一致，(code, market) 双键 map 天然覆盖 LOF 与 CASH/IN_TRANSIT 种子产品（`market=""`）。② **流程风险**：CI `cli-contract-check` 只校验 `response_fields.py ↔ openapi.json` 一致性，**不校验 `openapi.json ↔ 后端代码`**——openapi.json 必须由含改动的后端重新导出并随 PR 提交，靠 §5 自查清单兜底。③ `ir-cli` `SUMMARY_FIELDS["trade"]` **不**加 product_name（与 position 摘要不含 product_name 一致，终端宽度有限），契约中该字段无 `*` 前缀。 |
| #176 | 方案 A 采纳 | ① 场内判断字段 `trade.market === "CN_EXCHANGE"`，与后端 `cancel_trade` 判断完全一致。② confirmed 行删除按钮移除后，`CONFIRM_TEXT["delete"]` 原文案（「影响后续快照」针对 confirmed）须改写为 pending 语义（级联删配对现金腿、不可恢复）。③ `useDeleteTrade` 补 toast（用户已批准纳入）。 |

**合并冲突点分析（单分支策略下消解）**：三者在 `TradesContent.tsx` 的叠加按 commit 顺序天然分层——#173 动表头 + 金额 cell + 表单；#176 动操作 cell（pending/confirmed 块）+ CONFIRM_TEXT；#174 在 #176 重构后的 pending 块内加 Pencil、并新增独立 Dialog JSX 与 state。按 §2 的 commit 顺序实施，后改者总落在前者的结构上，无冲突。

**顺手改进（用户已批准纳入）**：① `useDeleteTrade` 补 toast（#176 范围）；② `useUpdateTrade` onSuccess 失效 `positions` 查询缓存，与 create/confirm 对齐（#174 范围）——改金额/日期后持仓页可用现金可能显旧值的问题一并消除。

---

## 1. 改动地图

| 层 | 文件 | 动作 | 归属 |
|---|---|---|---|
| backend | `app/schemas/trade.py` | `TradeResponse` 加 `product_name: Optional[str] = None`（读侧派生注释） | #175 |
| backend | `app/routers/trades.py` | `get_trades` 批量查 Product 建 name_map，items 序列化后挂 `product_name` | #175 |
| backend | `tests/integration/test_trades.py` | 新增 list 响应 `product_name` 断言（基金腿 + CASH 配对腿） | #175 |
| backend | `openapi.json` | 重新导出（含新 schema 字段） | #175 |
| ir-cli | `ir_cli/response_fields.py` | `gen_response_fields.py` 重新生成（trade.list 契约加 product_name） | #175 |
| frontend | `src/types/trade.ts` | `Trade` 加 `product_name?: string` | #175 |
| frontend | `src/components/shared/TradesContent.tsx` | 删 `useProductList`/`getProductName` 改读 `trade.product_name`；表单加 fee；表头/行/现金子行拆列；操作列按钮矩阵 + tooltip；编辑 Dialog 与 state | #173/#174/#175/#176 |
| frontend | `src/hooks/useTrade.ts` | 引入 `useUpdateTrade` 消费（TradesContent）；`useUpdateTrade` onSuccess 补 positions 缓存失效；`useDeleteTrade` 补成功/失败 toast | #174/#176 |

无 DB 迁移、无新依赖、无 CLI 命令变更。`AGENTS.md` 无需更新（无新设计决策；§2.2/§3.2 不变量均未触碰）。

---

## 2. 分阶段任务（commit 粒度）

### Commit 1 — `feat(trade): 交易列表读侧派生 product_name，根治分页上限名称回退 (#175)`

**backend/app/schemas/trade.py** — `TradeResponse` 尾部加字段：

```python
class TradeResponse(TradeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # product_name 读侧派生（非 DB 列）：仅 list 端点批量 join 产品表填充，
    # create/get/update/preview 响应恒为 None；同 positions 模式（#175）
    product_name: Optional[str] = None
```

- pydantic v2 `from_attributes` 对缺失属性回退默认值，create/get/update/preview 返回 ORM 对象不受影响（恒 None）。
- 不加进 `TradeBase`（避免写侧 schema 污染）。

**backend/app/routers/trades.py** — `get_trades`（L53-74）改为：

```python
items, total = list_trades(db, ...)
# 读侧派生 product_name（#175）：批量查当页产品建 name_map（防 N+1，
# 同 positions.py 模式）；(code, market) 双键天然覆盖 LOF 与 CASH 虚拟产品
pairs = {(t.product_code, t.market) for t in items}
name_map = {}
if pairs:
    codes = {c for c, _ in pairs}
    name_map = {
        (p.code, p.market): p.name
        for p in db.query(Product.code, Product.market, Product.name)
        .filter(Product.code.in_(codes))
        .all()
        if (p.code, p.market) in pairs
    }
enriched = []
for t in items:
    row = TradeResponse.model_validate(t).model_dump()
    row["product_name"] = name_map.get((t.product_code, t.market))
    enriched.append(row)
return {"items": enriched, "total": total, "page": page, "page_size": page_size}
```

- 不加 response_model（现状为 `{}`，enriched dict 与纯 TradeResponse 列表已不同构；包 list schema 属额外重构，YAGNI）。
- `mode="json"` 注意：`model_dump()` 产出 date/Decimal 对象，FastAPI `jsonable_encoder` 会处理（positions.py 同款写法已在线上验证）；如需保险可用 `model_dump(mode="json")`，以 positions.py 现有写法为准保持一致。

**backend/tests/integration/test_trades.py** — 新增用例：

- `test_list_trades_includes_product_name`：造组合 + 产品 + 一笔调仓（产生基金腿 + 配对 CASH 腿），`GET /api/trades?portfolio_code=...` 断言每条 item 含 `product_name` 且等于产品表 name（基金腿 = 基金名，CASH 腿 = CASH 种子产品名）。注释说明：>100 产品的回退是前端分页映射问题，后端 join 与产品总数无关，无需构造 100+ 产品。

**契约再生成（顺序固定，三步同 commit）**：

1. 重新导出 `backend/openapi.json`（必须由含新 schema 的代码导出）：
   - 首选（无需起服务/鉴权）：`cd backend && python -c "import json; from app.main import app; json.dump(app.openapi(), open('openapi.json','w'), ensure_ascii=False, indent=2)"`
   - 备选（文档路径）：起本地后端后 `python export_openapi.py`
   - 完成后 `git diff backend/openapi.json` 自查：预期仅 TradeResponse 增加 product_name（若出现大量无关 diff 说明基线 openapi.json 已漂移，须停下来报告，不擅自全量提交）。
2. `python ir-cli/scripts/gen_response_fields.py` 重新生成 `ir-cli/ir_cli/response_fields.py`。
3. `python ir-cli/scripts/gen_response_fields.py --check` 本地预跑 CI 校验。

**frontend/src/types/trade.ts** — `Trade` 接口加 `product_name?: string`（注释：读侧派生，仅 list 响应有值）。

**frontend/src/components/shared/TradesContent.tsx**：

- 删 `useProductList` import 与 L151 `productsData`、L156 `products`、L194-197 `getProductName`。
- L367 改 `{trade.product_name || trade.product_code}`（CASH 孤儿行走 `cashOrphanLabel` 不受影响）。

### Commit 2 — `feat(trades): 调仓表单手续费录入 + 列表金额/份额/手续费三列 (#173)`

全部在 `TradesContent.tsx`：

1. **formData**（L203-212）加 `fee: ""`；`resetTradeForm`（L219-222）同步重置。
2. **handleSubmit**（L226-238）payload 加 `fee: formData.fee ? parseFloat(formData.fee) : 0`（买入/卖出均适用；`TradeCreate.fee` 类型已存在）。
3. **表单 Dialog**：「价格」输入框（L633-643）与「交易日期」之间插入：

```tsx
<div className="space-y-2">
  <Label htmlFor="fee">手续费（元）</Label>
  <Input
    id="fee"
    type="number"
    step="0.01"
    value={formData.fee}
    onChange={(e) => setFormData({ ...formData, fee: e.target.value })}
    placeholder="默认 0"
  />
</div>
```

4. **表头**（L697-710）：`<TableHead className="text-right">金额/份额</TableHead>` 拆为三个 text-right 列：`金额` `份额` `手续费`（总列数 10 → 12）。
5. **renderMainRow**（L386-388）金额 cell 拆三 cell：

```tsx
<TableCell className="text-right">
  {trade.amount ? formatCurrency(trade.amount) : "-"}
</TableCell>
<TableCell className="text-right">
  {trade.shares ? formatShares(trade.shares) : "-"}
</TableCell>
<TableCell className="text-right">
  {trade.fee ? formatCurrency(trade.fee) : "-"}
</TableCell>
```

- 金额列 = `trade.amount`（净额，用户已定口径）；truthy 判断使 pending 卖出（amount≈0/fee、确认后才回填）显示 `-`；份额格式化用 `formatShares`（utils 已有，2 位小数）。
6. **renderCashSubRow**（L461-488）：金额 cell（保留 `meta.sign + formatCurrency`）后补两个空 `<TableCell />`（份额/手续费），总 cell 数对齐 12。
7. 导入加 `formatShares`。

### Commit 3 — `fix(trades): 操作按钮对齐后端允许矩阵 + pending 删除入口 (#176)`

**TradesContent.tsx** renderMainRow 操作 cell（L411-455）重构：

- **pending 行**（最终形态含 #174 的编辑位，本 commit 先三键）：
  - `✓ 确认`：所有 pending，加 `title="确认"`；
  - `✗ 取消`：仅 `trade.market !== "CN_EXCHANGE"` 渲染，加 `title="取消"`；
  - `🗑 删除`：所有 pending 新增，`onClick={() => setConfirmState({ action: "delete", id: trade.id })}`，加 `title="删除"`。
- **confirmed 行**：保留 `↩ 取消确认`（title 已有）与 `✎ 修改`（editHint 提示，行为不变，title 已有）；**删除 🗑 按钮整块移除**。
- **CONFIRM_TEXT**（L88-93）`delete` 文案改为 pending 语义：`{ title: "删除交易", desc: "删除将同时删除配对的现金记录，且不可恢复。是否继续？" }`（原「影响后续快照」文案针对 confirmed，已不适用）。
- 场内判断直接 `trade.market === "CN_EXCHANGE"`（与后端 `cancel_trade` 一致；前端无既有常量，不引入新文件）。

**useTrade.ts** `useDeleteTrade`（L199-208）补 toast（对齐 useCancelTrade 模式）：

```ts
export function useDeleteTrade() {
  const queryClient = useQueryClient();
  const addToast = useUIStore((state) => state.addToast);
  return useMutation({
    mutationFn: (id: number) => tradeApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, "list"] });
      addToast({ type: "success", title: "删除成功", message: "交易及其配对记录已删除" });
    },
    onError: (error: unknown) => {
      addToast({ type: "error", title: "删除失败", message: getErrorMessage(error, "操作失败，请重试") });
    },
  });
}
```

### Commit 4 — `feat(trades): pending 交易编辑 Dialog (#174)`

**useTrade.ts**（顺手改进 ②，用户已批准纳入）— `useUpdateTrade`（L85-108）onSuccess 补 positions 缓存失效，与 `useConfirmTrade` 对齐（update 响应为 TradeResponse，`data.portfolio_code` 可用）：

```ts
onSuccess: (data) => {
  queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, id] });
  queryClient.invalidateQueries({ queryKey: [TRADE_QUERY_KEY, "list"] });
  queryClient.invalidateQueries({ queryKey: ["positions", data.portfolio_code] });
  ...
```

**TradesContent.tsx**（hook 已就绪，仅需 import）：

1. **state**：`const [editingTrade, setEditingTrade] = useState<Trade | null>(null)` + `editFormData`（`amount`/`shares`/`price`/`fee`/`trade_date`/`notes` 全字符串，`trade_date` 默认 `toDateOnly(new Date())` 占位）。import 加 `useUpdateTrade`、`TradeUpdate` 类型。
2. **hook 调用**（顶层，遵守 hooks 规则）：`const updateTrade = useUpdateTrade(editingTrade?.id ?? 0)`（id=0 时 mutate 不会被触发）。
3. **打开编辑**：pending 行操作 cell 在 `✓` 前加 `✎` 按钮（顺序：编辑 → 确认 → 取消/删除），`title="编辑"`，`onClick` 置 `editingTrade` 并按方向预填：
   - buy：`amount: String(trade.amount ?? "")`；sell：`shares: String(trade.shares ?? "")`；
   - `price: trade.price != null ? String(trade.price) : ""`；`fee: trade.fee ? String(trade.fee) : ""`；`trade_date: trade.trade_date`；`notes: trade.notes ?? ""`。
4. **编辑 Dialog**（独立 `<Dialog open={!!editingTrade}>`，复用提交表单结构）：
   - 只读区：产品名+代码（`editingTrade.product_name || product_code`）、平台、方向 badge；
   - 字段：按 `editingTrade.trade_type` 渲染「金额（元）」或「份额」、价格、手续费（元）、交易日期（DatePicker）、备注（Input）；
   - 提交构造 `TradeUpdate`：仅组装非空字段（`parseFloat` 数字、`trade_date` 用 `toDateOnly`），空串字段不入 payload（`exclude_unset` 语义下避免误清）；
   - `updateTrade.mutate(payload, { onSuccess: () => setEditingTrade(null) })`；失败时 hook 已 toast，Dialog 保持打开可重试（不挂 onError 关闭逻辑）；
   - 提交按钮 disabled 条件：`updateTrade.isPending`。
5. confirmed 行 `✎` 保持 editHint 提示行为不变（验收断言要求）。

---

## 3. 测试方案

| 层 | 内容 |
|---|---|
| 后端单测/集成 | 新增 `test_list_trades_includes_product_name`（Commit 1）；全量 `pytest tests/ -q`（SQLite）回归 |
| 契约 | `python ir-cli/scripts/gen_response_fields.py --check` 本地通过（CI `cli-contract-check` 同命令） |
| 前端门禁 | `cd frontend && npm run build`（ESLint + tsc 0 error）；重点核对：`useProductList` 引用已清、`formatShares` 导入、hooks 顶层调用 |
| E2E（可选） | `frontend/e2e/regression.spec.ts` 现有交易页用例若有表头断言需同步更新；不新增用例（验收以手工为主，e2e fixture 交易数据不在本 PR 建设） |
| 手工冒烟 | 按 §4 验收自查清单逐条执行（开发库或本地起前后端） |

## 4. 验收自查清单（对照 issue 断言，逐条可勾选）

**#173**

- [ ] 打开「提交交易」对话框 → 出现「手续费（元）」输入框（位于价格与交易日期之间），留空提交 fee=0
- [ ] 输入手续费 5.5 提交 → 后端 trade 记录 fee=5.5
- [ ] 列表表头为「金额」「份额」「手续费」三列（替代原合并列）
- [ ] 买入行：金额列显示 amount（净额），份额列显示份额，手续费列显示 fee
- [ ] 卖出行：金额列显示 amount，份额列显示 shares，手续费列显示 fee
- [ ] CASH 结对子行正确对齐 12 列（份额/手续费空单元格占位）
- [ ] 移动端交易列表新增列正常（横滚可用）

**#174**

- [ ] pending 行操作列出现编辑按钮（Pencil 图标）
- [ ] 点击编辑 → Dialog 预填当前金额/份额、价格、手续费、交易日期、备注
- [ ] 改手续费提交 → 后端 fee 更新，列表刷新显示新值
- [ ] 改交易日期提交 → confirm_date 按产品 confirm_days 联动重算
- [ ] confirmed 行编辑按钮行为不变（仍弹「请先取消确认」提示）
- [ ] 编辑提交失败显示错误 toast，Dialog 保持打开可重试
- [ ] 编辑金额/日期提交成功后，持仓页可用现金同步刷新（positions 缓存已失效）

**#175**

- [ ] `GET /api/trades` 每条 item 含 `product_name`（含 CASH 配对腿）
- [ ] 产品总数 >100 时，交易列表产品列第一行产品名、第二行代码
- [ ] 早期种子产品（518880.SH 等）与新产品交易行均正确显示产品名
- [ ] 前端已移除分页产品列表名称映射（`getProductName`/`useProductList` 删除，改读 `trade.product_name`）
- [ ] `openapi.json` 与 `response_fields.py` 已重新生成，`gen_response_fields.py --check` 通过
- [ ] PORT001 与 PORT005 交易列表产品列展示一致

**#176**

- [ ] pending 场内行显示 🗑 删除，点击 → 交易及配对 CASH 腿删除、列表刷新、出现成功 toast
- [ ] pending 场内行不显示 ✗ 取消（不再触发 `CANNOT_CANCEL_EXCHANGE`）
- [ ] pending 场外行仍显示 ✗ 取消，点击 → status=cancelled
- [ ] confirmed 行不再显示删除按钮（保留 ↩ 取消确认 / ✎ 修改引导）
- [ ] 确认/取消/删除按钮均有 tooltip（title）标明动作

## 5. 风险与注意点

1. **openapi.json 漂移风险（最高优先级自查）**：CI 只校验 `response_fields.py ↔ openapi.json`，不校验 openapi.json 与后端代码一致。提交前必须 `git diff backend/openapi.json` 确认 diff 仅含 product_name 相关改动；若基线已漂移（出现无关 diff），停下来向用户报告，不擅自全量提交。
2. **deploy 顺序**：同 PR 内含「前端读 `trade.product_name` + 后端产出」，合并后 CI→CD 同时部署前后端，无中间态窗口问题；若后端部署失败而前端先行，产品列回退显示代码（`|| product_code` 兜底），可接受。
3. **金额列语义变更公告**：#173 后买入行金额列从「合并列的实际扣款」变为「净额 amount」，实扣 = 金额 + 手续费；为用户预期内变更（issue 已确认口径），PR 描述中写明。
4. **列宽**：12 列桌面表格为全站最宽表格之一，实施后在 1280px 视口目视检查是否挤压；移动端横滚既有行为覆盖。
5. **不纳入项**（防范围蔓延）：PUT 可用量/交易日校验（已提 issue #182）、`GET /api/trades` 补 response_model（已提 issue #183）——均为后端既有语义或额外重构，不进本 PR。
