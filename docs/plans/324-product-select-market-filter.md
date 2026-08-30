# #324 实施计划 — 提交交易产品选择器增加市场筛选（弹层内条件行）+ 联动一致性

> 本计划源自 Claude（session 3cd230c6）对 #324 的两轮评估：初始主方案评估（弹层内条件行 + MARKET_OPTIONS 抽共享 + E2E）+ 补充点联动评估（市场-产品联动一致性）。
> 决策（用户确认「开工」）：
> - 放置：**弹层内条件行**（搜索框与列表之间一行 Select，默认「全部市场」，重开复位）——不做表单级字段
> - 联动语义：**筛选状态不持久**（点选即弃 + 重开复位「全部市场」），**不做** market 同步、**不加**拦截
> - 筛选项：静态四项（全部市场/A股场内/内地场外/香港互认）
> - 复用：#259 已落地的 `product-option`/`data-code`/`data-market` 钩子 + LOF 种子

## 目标

提交交易产品选择器 `SearchableProductSelect` 弹层内增加市场筛选，直击 LOF 一码多市场歧义。市场是歧义的本质维度（161017 场内/场外 market 不同），按市场过滤后**数据层消除歧义**。零后端改动（`routers/products.py` L39-40 已支持 market 过滤）。

## 改动清单

### 1. `frontend/src/lib/market.ts`（新建，抽共享 MARKET_OPTIONS）

从 `ProductFilterDialog.tsx` L53-56 与 `ProductsContent.tsx` L61 的重复定义抽取到共享模块：
```ts
export const MARKET_OPTIONS = ["CN_EXCHANGE", "CN_OTC", "HK_MUTUAL"].map((v) => ({
  value: v,
  label: formatMarketName(v),
}));
```

### 2. `frontend/src/components/shared/SearchableProductSelect.tsx`（核心改动）

**⚠️ 关键技术点（已由 Hermes 调研确认）**：本仓库 `Popover` 默认 `modal=false`（`popover.tsx` 未覆盖，Radix `react-popover` 源码 L37），而 `Radix Select` 是 **modal** 组件（`select.tsx` 未覆盖 `modal`）。Select 打开时焦点移到其 portal（位于 Popover 外），会触发外层 Popover 的 focus-outside，可能导致 Popover 意外关闭。**标准解法**：给本组件使用的 `PopoverContent` 增加 `onInteractOutside={(e) => e.preventDefault()}`（阻止焦点/点击移出时关闭 Popover），参考 Radix 社区公认方案。若实施中发现其他交互问题，同样以「阻止 Popover 在内部 Select 交互时关闭」为原则处理。

在弹层内搜索框下方增加「市场」条件行：
- 新增局部 state `market`（默认 `undefined` = 全部市场）
- `useProductList` 的入参增加 `market: market || undefined`（透传，queryKey 带参数自动刷新）
- 在搜索框与列表之间加一行 Select（参考 `ProductFilterDialog` L235-250 的模式）：选项为「全部市场」/`MARKET_OPTIONS` 三项；`onValueChange` 设 `setMarket(v === "all" ? undefined : v)`
- **联动一致性**（补充点结论）：
  - 筛选**不持久**：弹层关闭时（`onOpenChange(false)`）或重开时复位 `market` 为 `undefined`（复用 ProductFilterDialog 的复位语义）
  - 点选即弃：点选产品后关闭弹层，下次打开复位「全部市场」
  - **不做**选中产品后同步 market、**不加**拦截
- `MARKET_OPTIONS` 改从 `@/lib/market` 导入（去掉组件内本地定义）

### 3. 依赖去重（顺带）

`ProductFilterDialog.tsx` L53-56 与 `ProductsContent.tsx` L61 的 `MARKET_OPTIONS` 改为从 `@/lib/market` 导入（三处共用，去重）。

### 4. `frontend/e2e/product-select-market.spec.ts`（扩展，或新建市场筛选 spec）

基于 #259 已有的 spec 扩展，或新增市场筛选相关用例：
- 打开弹层 → 出现「市场」筛选（默认「全部市场」），选项为全部市场/A股场内/内地场外/香港互认四项
- 选「A股场内」→ 请求带 `market=CN_EXCHANGE`（`waitForResponse` 拦截体验证，参考 platform-select-search.spec.ts 同款模式）；列表只含场内产品
- 选「内地场外」→ 只含 `CN_OTC`，**虚拟产品（CASH/IN_TRANSIT*）不出现**（`market=""` 自然排除）
- LOF 161017 双市场：选「内地场外」→ 仅显示 161017.OF 一条
- **联动断言**（补充点）：选中 161017.OF 关闭弹层后重开 → 市场筛选显示「全部市场」（非"内地场外"）、已选回显完整、触发按钮市场徽章为「内地场外」
- **提交载荷不变量**：经任意筛选浏览路径后点选并提交，POST 载荷的 `market` 恒等于点选项的 market（E2E 拦截请求体验证）
- 移动端复跑（组件双端共享，自动覆盖）
- 遵循「优雅 skip」惯例

## 验证

- `npm run build`（tsc + ESLint 门禁，0 error）
- 后端 `pytest`（无后端改动，回归确认）
- `npm run test:e2e` 相关 spec
- 视觉规范自查：Select 样式对齐现有条件行；无新增字号/色值

## 边界

- **零后端改动**（`market` 过滤已存在）
- **不做**虚拟产品默认视图排除（另立 issue，需后端排除参数）
- **不做**表单级字段、**不做** market 同步、**不加**拦截
- 不 push / 不建 PR / 不发 issue 评论（由编排者处理）
- 完成后 git commit（消息遵循仓库惯例，`fixes #324`）
