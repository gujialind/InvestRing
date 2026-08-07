
# 修复方案：Issue #105 + #106

## 关键约束
- #106 的「最新收益 (MM-DD)」后缀取自行 `snapshot_date`，依赖 #105 修复后默认查询各行 snapshot_date 一致（均为组合最新快照日）。故 **#105 必须先于 #106 实施与合入**。
- 两 issue 同属 positions 读侧，放同一分支 `feature/105-106-positions-default-query` 提交，PR 描述注明 `fixes #105, fixes #106`。

---

## 第一部分：Issue #105 — positions 默认查询改为组合级最新快照日

### 改动文件
**`backend/app/routers/positions.py`**（第 39-54 行）

当前子查询按 `(portfolio_code, product_code)` 分组取 max(snapshot_date)，改为按 `portfolio_code` 分组取 max(snapshot_date)。

```python
# 当前（错误）：
subq = (
    db.query(
        PortfolioPosition.portfolio_code,
        PortfolioPosition.product_code,
        func.max(PortfolioPosition.snapshot_date).label("max_date"),
    )
    .group_by(PortfolioPosition.portfolio_code, PortfolioPosition.product_code)
    .subquery()
)
query = query.join(
    subq,
    (PortfolioPosition.portfolio_code == subq.c.portfolio_code)
    & (PortfolioPosition.product_code == subq.c.product_code)
    & (PortfolioPosition.snapshot_date == subq.c.max_date),
)

# 修复后：
subq = (
    db.query(
        PortfolioPosition.portfolio_code,
        func.max(PortfolioPosition.snapshot_date).label("max_date"),
    )
    .group_by(PortfolioPosition.portfolio_code)
    .subquery()
)
query = query.join(
    subq,
    (PortfolioPosition.portfolio_code == subq.c.portfolio_code)
    & (PortfolioPosition.snapshot_date == subq.c.max_date),
)
```

注释同步从「每个组合每个产品的最新日期」改为「每个组合的最新快照日」。

### 新增测试
**`backend/tests/integration/test_positions.py`** — 新增 `TestPositionLatestSnapshot` 类：

1. **`test_cleared_product_excluded_from_default_query`**：组合有两个快照日（d1 有基金 F1 持仓 + CASH，d2 仅 CASH 无 F1），不传 snapshot_date 默认查询 → 返回行不含 F1，仅 CASH 行且 snapshot_date == d2。
2. **`test_in_transit_removed_excluded_from_default_query`**：d1 有 IN_TRANSIT_BUY 行，d2 无（在途消除），默认查询 → 不含 IN_TRANSIT_BUY。
3. **`test_multi_portfolio_different_snapshot_dates`**：两个组合各自最新快照日不同，不传 portfolio_code 全局查询 → 各组合返回行 snapshot_date 分别等于各自最新快照日（评审补充断言）。
4. **`test_explicit_snapshot_date_unchanged`**：显式传 snapshot_date=d1 查询历史 → 行为不变，返回 d1 的行（含已清仓产品）。

---

## 第二部分：Issue #106 — 持仓卡片与设计稿对齐

### 2.1 后端补 platform_name 字段

**`backend/app/schemas/position.py`**（PositionResponse 类，第 49-51 行附近）：
```python
platform_name: Optional[str] = None
```

**`backend/app/routers/positions.py`**（get_positions enrich 段，第 87-105 行附近）：
在现有 `codes` 批量查询之后，新增 platform_code → name 批量查询（防 N+1），沿用 product_name enrich 模式：

```python
# platform_name 批量 enrich（防 N+1）
platform_codes = {p.platform_code for p in items if p.platform_code}
platform_name_map = {}
if platform_codes:
    for plat in db.query(Platform.code, Platform.name).filter(Platform.code.in_(platform_codes)).all():
        platform_name_map[plat.code] = plat.name
```

文件头部新增 `from app.models.platform import Platform`。

enrich 循环中新增：
```python
row["platform_name"] = platform_name_map.get(p.platform_code) if p.platform_code else None
```

**`backend/openapi.json`**：改动后执行 `python export_openapi.py` 重新生成（CI 做一致性校验）。

### 2.2 前端 Position 类型

**`frontend/src/types/position.ts`**（Position interface，第 7 行后）：
```typescript
platform_name?: string | null;
```

### 2.3 前端 PositionSections 卡片重构

**`frontend/src/components/shared/PositionSections.tsx`**

#### PositionCard 组件（第 34-106 行）

按预览稿三行结构重写：

**row1**（资产短名目 + 金额 + 占比）：
- 左：`asset_name`（缺省回退 `product_name` → `product_code`）
- 右：`formatNumber(amount)` 元 + `{percent.toFixed(1)}%`

**row2**（产品全称 + 代码 + 平台徽标）：
- `product_name`（缺省回退 `product_code`）
- `product_code`（tabular-nums）
- 平台徽标（ml-auto）：`platform_name`（缺省回退 `platform_code`）

**metrics 行**（三列并列）：
- 列 1「持仓金额」：`formatNumber(amount)`，neutral 色
- 列 2「累计收益」：`formatProfit(position.profit_loss)`，涨跌色
- 列 3「最新收益 (MM-DD)」：`formatProfit(position.daily_profit)`，涨跌色；标签从 `snapshot_date`（格式 "2025-11-04"）提取 `MM-DD` 拼接；保留 QDII tooltip

```typescript
// MM-DD 提取
const mmdd = position.snapshot_date
  ? position.snapshot_date.slice(5, 10).replace("-", "/")
  : "";
// 标签：`最新收益 (${mmdd})`
```

#### 在途资金卡片（第 211-238 行）

- row2 徽标：`platform_name`（缺省回退 `platform_code`），替换当前 `platform_code`
- 无 metrics 行（在途卡片只有 row1 + row2）

### 2.4 新增测试

**后端**（`test_positions.py`）：
- **`test_platform_name_enriched`**：持仓行含 platform_code，响应 `platform_name` 等于 Platform 表对应 name；platform_code 为 null 时 platform_name 也为 null。
- **`test_platform_name_sql_count_constant`**：用 `patch.object` 包装 `db.query` 或统计 SQL 次数，断言 platform_name enrich 查询次数恒定（不随持仓行数增长），沿用 `test_aggregate_flows_called_once` 模式。

**前端**：ESLint + tsc 构建 0 error（质量门禁）。

---

## 测试计划
1. 后端 SQLite pytest：`cd backend && python -m pytest tests/integration/test_positions.py tests/integration/test_in_transit.py -v`
2. 后端 openapi 一致性：`cd backend && python export_openapi.py && git diff --exit-code openapi.json`（或 CI 校验）
3. ir-cli 契约：`cd ir-cli && python scripts/gen_response_fields.py && git diff --exit-code`（或 CI 校验）
4. 前端构建：`cd frontend && npm run build`（含 ESLint + tsc）

## 假设
- 设计稿预览文件（`.qoder/preview/portfolio-holdings-preview*.html`）为对齐基准，不改动。
- `positionAmount` 已正确返回行金额（净值型取 market_value，现金/在途取 cash_amount），metrics 列 1「持仓金额」直接复用。
- MM-DD 格式为 `MM/DD`（如 `08/04`），从 `snapshot_date` 字符串 `YYYY-MM-DD` 截取。
