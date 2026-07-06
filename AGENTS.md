# InvestRing 模块开发指南

> 版本：v3.1
> 更新日期：2026-06-26
> 用途：为 AI 编程助手提供核心业务规则、约束边界与模块级开发规范的快速参考。前端架构详见 §2.3，详细技术文档参阅 `Docs/` 目录（见 §5.1）。

---

## 目录

1. [核心业务规则](#1-核心业务规则)
2. [模块总览](#2-模块总览)
3. [关键约束与边界](#3-关键约束与边界)
4. [重要提醒清单](#4-重要提醒清单)
5. [文档引用](#5-文档引用)
6. [附录](#附录快速参考)

---

## 1. 核心业务规则

### 1.1 快照模式（最重要）

**三张快照表，只增不改**：
- `portfolio_value_snapshot`：组合市值快照
- `investor_holding`：投资人份额快照  
- `portfolio_position`：持仓快照

**规则**：
- 快照每天汇总生成一次，不是每笔交易生成
- 生成前提：净值和分红事件更新完成 + 当天应确认交易都已处理完
- 查询当前状态：`WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM ...)`
- 快照永不 UPDATE，保留完整历史
- **快照生成固定顺序**：`portfolio_position` → `portfolio_value_snapshot` → `investor_holding`

### 1.2 冻结机制

**冻结字段实时计算**：
- 赎回冻结份额：`SUM(subscription.shares) WHERE sub_type='redeem' AND status='pending'`
- 卖出冻结份额：`SUM(trade.shares) WHERE trade_type='sell' AND status='pending'`
- 买入冻结金额：`SUM(trade.amount) WHERE trade_type='buy' AND status='pending'`

**可用份额/现金必须实时计算**，不能仅读取快照中的 frozen 字段。

**可用现金实时计算**：
```
组合可用现金 = 最新快照现金
            + SUM(confirmed申购金额 WHERE 快照未生成)
            - SUM(confirmed赎回金额 WHERE 快照未生成)
            - SUM(pending买入金额)
            - SUM(confirmed买入金额 WHERE 快照未生成)
            + SUM(confirmed卖出金额 WHERE 快照未生成)
```

**基金可用份额实时计算**：
```
基金可用份额 = 最新快照份额
            - SUM(pending卖出份额)
            - SUM(confirmed卖出份额 WHERE 快照未生成)
```

**投资人可用份额实时计算**：
```
投资人可用份额 = 最新快照份额
              - SUM(pending赎回份额)
              - SUM(confirmed赎回份额 WHERE 快照未生成)
```

### 1.3 组合净值管理原则

- **初始净值固定为 1.0000**：首次申购确认时净值 = 1.0000，份额 = 金额
- **净值稳定性**：
  - 申购：份额和市值同步增加 → 净值不变
  - 赎回：按申请日净值计算 → 净值不变
  - 调仓：不同基金净值波动不同 → 净值可能变化
  - 现金分红/份额拆分/合并：份额和净值同步调整 → 净值不变
- **市值计算**：`总市值 = Σ(场内份额 × 收盘价) + Σ(场外份额 × 净值) + Σ(非净值型资产金额)`
- **净值计算**：`unit_price = total_value / total_shares`（保留 4 位小数）
- **成本价计算**：首次 = 组合净值；后续 = `(old×cost + new×price) / (old + new)`

### 1.4 现金中转约束（调仓）

**调仓必须通过现金中转，不能直接基金对基金转换**：
- 卖出基金：所得资金进入组合现金池（需等待确认）
- 买入基金：从组合现金池支出（只能使用已有可用现金）
- 卖出 pending **不自动增加可用现金**
- 现金不足时需分两步操作（先卖后买）

### 1.5 交易日校验

所有交易操作（申购、赎回、调仓、现金进出）仅允许在交易日进行。
非交易日提交交易返回错误：`{ error: "NON_TRADING_DAY", message: "非交易日，请等待交易日再提交" }`

交易日判断：查询 `trading_calendar` 表 `is_open = true`。

---

## 2. 模块总览

### 2.1 后端模块（14 个）

| 编号 | 模块 | 接口数 | 权限 | 核心功能 |
|------|------|--------|------|----------|
| 1 | 认证模块 | 2 | 公开 | 登录、修改密码 |
| 2 | 投资人管理 | 5 | admin | CRUD + 移除 |
| 3 | 组合管理 | 11 | admin | 创建/状态流转/净值计算 |
| 4 | 持仓管理 | 10 | 所有用户 | 持仓/收益/可用现金/归因分析 |
| 5 | 申购赎回管理 | 7 | admin | 申请/确认/取消 |
| 6 | 调仓交易管理 | 8 | admin | 买入/卖出/确认/批量调仓 |
| 7 | 份额变动事件 | 7 | admin | 创建/确认/取消分红等事件 |
| 8 | 市场数据 | 4 | admin | 产品价格查询/同步（含净值同步） |
| 9 | 产品管理 | 8 | admin | CRUD + 数据源验证 |
| 10 | 平台管理 | 4 | admin | 平台 CRUD |
| 11 | 系统管理 | 4 | admin | 交易日历/数据源配置 |
| 12 | 系统日志（V2） | 5 | admin | 登录/审计/任务/错误日志 |
| 13 | 任务管理（V2） | 4 | admin | 任务启停/手动触发 |
| 14 | 通知（V2） | 3 | 所有用户 | 通知列表/标记已读 |

### 2.2 前端页面（13 个）

| 编号 | 页面 | 可见角色 | 说明 |
|------|------|----------|------|
| 1 | 登录页 | 所有用户 | 双端共用 |
| 2 | 首页（Dashboard） | 所有用户 | 组合概览、净值曲线 |
| 3 | 投资人管理页 | admin | 投资人 CRUD |
| 4 | 组合列表页 | 所有用户 | 默认显示活跃组合 |
| 5 | 组合详情页 | 所有用户 | 净值、收益、操作入口 |
| 6 | 持仓管理页 | 所有用户 | 持仓列表、调仓按钮 |
| 7 | 申购赎回页 | admin | 申购/赎回申请与记录 |
| 8 | 调仓交易页 | admin | 买入/卖出/批量调仓 |
| 9 | 产品管理页 | admin | 产品 CRUD |
| 10 | 平台管理页 | admin | 平台 CRUD |
| 11 | 设置页 | admin | 系统设置 |
| 12 | 日志管理页（V2） | admin | 各类日志查询 |
| 13 | 任务管理页（V2） | admin | 定时任务管理 |

### 2.3 前端架构要点

**技术栈**：Next.js 15 (App Router) + React 19 + shadcn/ui + TailwindCSS v4 (CSS-first 配置) + Zustand v5 + @tanstack/react-query v5 + TypeScript 5.6

**双端独立路由**：
- 移动端：`/m/` 前缀（如 `/m/dashboard`, `/m/portfolio/PORT001`）
- PC端：根路径（如 `/dashboard`, `/portfolio/PORT001`）
- Middleware 根据 User-Agent 自动重定向

**组件复用策略**（三层层级）：
- 完全共享：数据层(`hooks/`)、状态管理(`stores/`)、UI 原子组件(`components/ui/`)、类型定义(`types/`)
- 共享业务组件（`components/shared/`）：双端共用的页面级业务逻辑，通过 `variant: "desktop" | "mobile"` + `basePath` prop 适配两端布局与链接前缀。含 `LoadingState`/`EmptyState`/`StatCard` 等基础件，`PortfolioListContent`/`TradesContent`/`SubscriptionsContent` 等整页内容组件，`PortfolioStatsCards`/`PortfolioActionButtons`/`DashboardStatsCards` 等复合组件，以及 `dialogs/` 下的 `ClosePortfolioDialog`/`DeletePortfolioDialog`
- 独立实现：布局组件(`components/mobile/` vs `components/desktop/`、`components/layout/`)、各端页面入口(`app/m/` vs `app/`，仅负责套 Layout + 渲染共享内容组件)

**API 层**：`lib/api/` 按业务域拆分为 15 个模块（`auth`/`investor`/`portfolio`/`position`/`subscription`/`trade`/`product`/`platform`/`system`/`snapshot`/`share-change-event`/`log`/`task`/`notification` + 共享 `client`），通过 barrel `index.ts` 统一导出，保持 `@/lib/api` 导入路径兼容。`client.ts` 提供 `ApiException`/`handleApiError`/`getErrorMessage` 统一错误处理。

**质量保障**：ESLint v9 flat config（`eslint.config.mjs`），`npm run lint` 即 `eslint .`；构建期间强制 lint + tsc 类型检查，0 error 才可通过 `next build`。

---

## 3. 关键约束与边界

### 3.1 申购赎回边界

| 条件 | 处理方式 |
|------|---------|
| 申购金额为 0 | 拒绝创建 |
| 赎回份额 > 可用份额 | 拒绝（实时计算可用份额） |
| 组合现金不足 | 需先卖出持仓或拒绝 |
| 全部赎回 | 检查是否最后一位投资人 |
| 用户取消 | status = "cancelled" |

**输入单位**：
- 申购：输入**金额**（元），系统计算份额 = 金额 / T日净值
- 赎回：输入**份额**（份），系统计算金额 = 份额 × T日净值
- 赎回按**申请日净值**计算，不是确认日净值

### 3.2 调仓交易边界

| 条件 | 处理方式 |
|------|---------|
| 卖出份额 > 可用份额 | 拒绝 |
| 买入金额 > 可用现金 | 拒绝 |
| 买入金额为 0 | 拒绝 |
| 买入金额 > 已有现金 + 卖出 pending 金额 | 拒绝（卖出 pending 不增加可用现金） |
| 更新非净值资产缺少平台 | 拒绝，平台为必填项 |
| 更新日期不是交易日 | 拒绝，必须在交易日进行 |

**金额计算**：
- 买入：`amount = actual_amount - fee`，`shares = amount / price`
- 卖出：`amount = actual_amount + fee`，`shares = amount / price`

**确认规则**：
- 场内：当天确认（使用收盘价）
- 场外：T+1确认（使用T日净值）
- QDII：T+2确认

### 3.3 组合管理边界

| 条件 | 处理方式 |
|------|---------|
| 移除投资人时份额 > 0 | 拒绝，需先全部赎回 |
| 关闭时有待处理交易 | 拒绝，需先处理完 |
| 多投资人首次申购并发 | 数据库事务锁，按确认顺序 |

**组合状态流转**：
- `draft`（创建时）→ `active`（首次申购确认后）→ `closed`（执行关闭流程后）
- 已关闭组合禁止申购/赎回/调仓，但可查询历史记录
- 重新激活：仅已关闭组合可激活，激活后可正常操作

### 3.4 份额变动事件边界

| 条件 | 处理方式 |
|------|---------|
| 权益登记日不是交易日 | 拒绝创建事件 |
| 确认事件时持仓快照不存在 | 返回 `MISSING_POSITION_SNAPSHOT` 错误 |

**事件类型与计算**：

| event_type | 份额变化 | 现金变化 | 计算公式 |
|------------|---------|---------|---------|
| cash_dividend | 不变 | 增加 | cash_change = entitlement_shares × div_cash |
| reinvest_dividend | 增加 | 不变 | shares_change = entitlement_shares × div_cash / reinvest_nav |
| share_split | 增加 | 不变 | shares_after = entitlement_shares × ratio |
| share_merge | 减少 | 不变 | shares_after = entitlement_shares / ratio |
| bonus_share | 增加 | 不变 | shares_change = entitlement_shares × ratio |
| forced_adjustment | 指定 | 指定 | 直接填写 shares_change / cash_change |

---

## 4. 重要提醒清单

1. **快照每天汇总生成一次**：不是每笔交易生成，前提是 `apply_date < target_date` 的申购均已确认（`apply_date == target_date` 的 pending 申购不阻塞当日快照）
2. **冻结信息实时计算**：查询时汇总 pending 状态的交易，不写入快照
3. **所有交易必须校验交易日**：非交易日拒绝操作
4. **赎回按申请日净值**：不是确认日净值
5. **LOF 拆分为两条记录**：场内/场外分别处理
6. **首次申购净值固定 1.0000**：无需获取净值数据
7. **QDII 净值处理规则**：
   - 调仓交易确认：必须使用T日净值，若未同步则拒绝确认（禁止向前查找）
   - 快照生成/市值计算：使用T-1日（前一交易日）净值
   - 数据校验：QDII检查T-1日净值是否存在
8. **所有用户必须设置密码**：无免密登录
9. **所有资产人民币计价**：无汇率换算
10. **移动端优先**：前端路由 `/m/` 前缀
11. **调仓必须现金中转**：卖出 pending 不增加可用现金，买入只能用已有现金
12. **组合份额仅因申购赎回变化**：分红再投资只影响成分基金份额
13. **投资人不支持物理删除**：只能从组合中移除（份额需为 0）
14. **组合列表默认显示活跃组合**：已关闭组合通过筛选器访问
15. **MySQL 连接池配置**：使用 QueuePool 连接池，连接复用和自动回收
16. **快照生成固定顺序**：`portfolio_position` → `portfolio_value_snapshot` → `investor_holding`
17. **幂等性缓存 24 小时过期**：批量调仓使用 `Idempotency-Key`
18. **任务执行必须记录日志**：创建 `task_execution_log` 记录，更新状态
19. **组合关闭前检查**：pending交易、投资人份额、持仓状态
20. **移除投资人创建特殊快照**：shares=0，标记已退出，后续快照跳过
21. **非净值资产更新必须指定平台**：更新现金等非净值型资产时，platform_code 为必填项，同一组合可在不同平台分别持有现金
22. **快照删除自动级联回退**：删除D日快照时自动回退 `confirm_date==D` 的申购至 pending，清空确认相关字段
23. **快照重算自动重确认**：重算每个交易日后自动确认 `apply_date==D` 的 pending 申购，单笔失败不影响整批
24. **申购取消确认快照保护**：unconfirm 前检查 confirm_date 及之后是否已有快照，有则拒绝（`SNAPSHOT_DEPENDENCY`）

---

## 5. 文档引用

### 5.1 详细技术文档

| 文档路径 | 内容 |
|----------|------|
| `AGENTS.md` §2.3 | 前端架构、技术栈、组件复用策略、API 层、质量保障 |
| `Docs/00-开发总览.md` | 开发阶段、核心规则总结 |
| `Docs/02-数据库设计.md` | 21 张表完整结构、索引定义、外键约束、MySQL 连接池配置 |
| `Docs/03-业务流程设计.md` | 详细业务流程图、状态机、每日计算流程 |
| `Docs/04-后端开发.md` | 89 个 API 接口完整规范、枚举值定义、错误码、分页规范 |
| `Docs/05-前端开发.md` | 前端架构、组件策略、页面设计、路由规则 |
| `Docs/07-日志系统设计.md` | 日志/任务系统设计 |

### 5.2 核心枚举值

| 枚举类型 | 取值 | 说明 |
|----------|------|------|
| `investor.role` | `admin`, `viewer` | 管理员/投资人 |
| `portfolio.status` | `draft`, `active`, `closed` | 组合状态 |
| `product.product_type` | `ETF`, `OEF`, `LOF`, `CASH` | 产品类型 |
| `product.market` | `CN_EXCHANGE`, `CN_OTC`, `HK_MUTUAL`, `NULL` | 市场类型 |
| `trade.trade_type` | `buy`, `sell` | 交易类型 |
| `subscription.sub_type` | `subscribe`, `redeem` | 申购/赎回 |
| `status` | `pending`, `confirmed`, `cancelled` | 交易状态 |
| `event_type` | `cash_dividend`, `reinvest_dividend`, `share_split`, `share_merge`, `bonus_share`, `forced_adjustment` | 份额变动事件类型 |
| `data_source_status` | `pending`, `success`, `failed` | 数据源状态 |

### 5.3 关键错误码

| 错误码 | HTTP 状态码 | 场景 |
|--------|-------------|------|
| `NON_TRADING_DAY` | 422 | 非交易日提交交易 |
| `MISSING_POSITION_SNAPSHOT` | 422 | 权益登记日持仓快照不存在 |
| `INSUFFICIENT_SHARES` | 422 | 赎回/卖出份额不足 |
| `INSUFFICIENT_CASH` | 422 | 买入现金不足 |
| `PORTFOLIO_NOT_ACTIVE` | 422 | 组合未激活 |
| `PENDING_TRANSACTIONS_EXIST` | 422 | 存在待处理交易 |
| `INVESTOR_HAS_SHARES` | 422 | 投资人仍持有份额 |
| `INVALID_ENTITLEMENT_DATE` | 422 | 权益登记日不是交易日 |
| `NAV_NOT_AVAILABLE` | 422 | 申请日组合快照不存在，请先生成快照 |
| `SNAPSHOT_DEPENDENCY` | 422 | 申赎已被快照纳入，请先删除对应快照 |

**HTTP状态码通用定义**：
- 400：参数错误
- 401：未认证
- 403：无权限
- 404：资源不存在
- 409：资源冲突（如重复创建）
- 422：业务规则校验失败
- 500：服务器内部错误

### 5.4 分页规范

**请求参数**：`page`（默认1）, `page_size`（默认20，最大100）

**响应格式**：
```json
{ "items": [...], "total": number, "page": number, "page_size": number }
```

---

## 附录：快速参考

### A. 21 张数据库表分类

| 类别 | 表名 |
|------|------|
| 核心业务（13张） | `investor`, `portfolio`, `investor_holding`, `platform`, `product`, `asset_classification`, `portfolio_position`, `subscription`, `trade`, `price_record`, `share_change_event`, `portfolio_value_snapshot`, `trading_calendar` |
| 日志系统（7张） | `login_log`, `audit_log`, `scheduled_task`, `task_execution_log`, `nav_sync_detail`, `system_error_log`, `notification` |
| 其他（1张） | `idempotency_cache` |

### B. 定时任务清单

| 任务编码 | Cron 表达式 | 说明 |
|----------|-------------|------|
| `nav_sync` | `0 7 * * 1-5` | 每个交易日 07:00 同步净值数据（增量同步） |
| `trading_calendar_sync` | `0 2 1 1 *` | 每年 1 月 1 日 02:00 同步新年交易日历 |
| `log_cleanup` | `0 4 * * 0` | 每周日 04:00 清理过期日志 |

### C. 产品确认天数规则

| 条件 | confirm_days | 说明 |
|------|-------------|------|
| market = CN_EXCHANGE | 0 | 场内交易，当天确认 |
| market = CN_OTC 且 is_qdii = FALSE | 1 | 场外基金，T+1确认 |
| market = CN_OTC 且 is_qdii = TRUE | 2 | QDII基金，T+2确认 |

### D. 资产分类标准（18条）

| code | asset_type | asset_category | asset_subcat |
|------|------------|----------------|--------------|
| STOCK_CN_LARGE | 股票 | 国内股票 | 大盘 |
| STOCK_CN_SMALL | 股票 | 国内股票 | 中小盘 |
| STOCK_CN_VALUE | 股票 | 国内股票 | 价值 |
| STOCK_CN_GROWTH | 股票 | 国内股票 | 成长 |
| STOCK_CN_MIXED | 股票 | 国内股票 | 综合 |
| STOCK_HK_LARGE | 股票 | 港股 | 大盘 |
| STOCK_HK_SMALL | 股票 | 港股 | 中小盘 |
| STOCK_US | 股票 | 美股 | 美股 |
| STOCK_EU | 股票 | 欧洲 | 欧洲 |
| STOCK_JP | 股票 | 日本 | 日本 |
| STOCK_GLOBAL | 股票 | 海外股票 | 全球 |
| BOND_SHORT | 债券 | 国内债券 | 短债 |
| BOND_LONG | 债券 | 国内债券 | 中长债 |
| BOND_MIXED | 债券 | 国内债券 | 综合债 |
| BOND_US | 债券 | 国际债券 | 美债 |
| BOND_GLOBAL | 债券 | 国际债券 | 全球 |
| GOLD | 黄金 | 黄金 | 黄金 |
| CASH | 现金 | 现金 | 现金 |

### E. 外键约束行为

| 父表 | 子表 | 约束字段 | 删除行为 |
|------|------|----------|----------|
| `portfolio` | `portfolio_position` | `portfolio_code` | RESTRICT |
| `portfolio` | `portfolio_value_snapshot` | `portfolio_code` | RESTRICT |
| `portfolio` | `investor_holding` | `portfolio_code` | RESTRICT |
| `portfolio` | `subscription` | `portfolio_code` | RESTRICT |
| `portfolio` | `share_change_event` | `portfolio_code` | RESTRICT |
| `product` | `portfolio_position` | `(code, market)` | RESTRICT |
| `product` | `price_record` | `(code, market)` | RESTRICT |
| `product` | `trade` | `(code, market)` | RESTRICT |
| `investor` | `investor_holding` | `investor_code` | RESTRICT |
| `investor` | `subscription` | `investor_code` | RESTRICT |
| `platform` | `portfolio_position` | `platform_code` | RESTRICT |
| `platform` | `trade` | `platform_code` | RESTRICT |

**说明**：所有实体均采用 RESTRICT 策略，通过业务流程（关闭/停用）来管理生命周期，保留历史数据。

**唯一约束说明**：
- `portfolio_position` 表唯一约束：`(portfolio_code, product_code, market, platform_code, snapshot_date)`
- 支持同一组合在同一天通过不同平台持有相同产品的多条记录

### F. MySQL 连接池配置

```python
# SQLAlchemy MySQL 连接配置
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

DATABASE_URL = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,              # 连接池大小
    max_overflow=20,           # 最大溢出连接数
    pool_pre_ping=True,        # 连接前检测连接有效性
    pool_recycle=3600,         # 连接回收时间（秒）
    pool_timeout=30,           # 获取连接超时时间（秒）
)
```

**配置要点**：
- 连接池支持更好的并发性能
- 自动检测失效连接并重新建立
- 适用场景：读多写少的企业应用

### G. 核心计算公式

**收益率计算**：
- 累计收益率：`(当前净值 - 初始净值) / 初始净值 × 100%`
- 年化收益率：`(当前净值 / 初始净值)^(365 / 持有天数) - 1`
- 时间加权收益率（TWR）：`(1 + r₁) × (1 + r₂) × ... × (1 + rₙ) - 1`

**资金流计算**：
- 资金流入 = Σ(subscription.amount WHERE sub_type='subscribe' AND status='confirmed')
- 资金流出 = Σ(subscription.amount WHERE sub_type='redeem' AND status='confirmed')
- 净流入 = 资金流入 - 资金流出

**QDII净值获取**：

```python
# 场景1：调仓交易确认时获取QDII净值
def get_nav_for_trade_confirmation(product_code, trade_date):
    """
    调仓交易确认：必须使用T日净值，禁止向前查找
    """
    if not is_qdii(product_code):
        return query_price(product_code, trade_date)
    
    # QDII：必须取T日净值
    nav = query_price(product_code, trade_date)
    if not nav:
        raise ValueError(
            f"QDII产品{product_code}在T={trade_date}的净值尚未同步，"
            f"请等待T+2日后重试或手动指定净值"
        )
    return nav


# 场景2：快照生成/市值计算时获取QDII净值
def get_nav_for_portfolio_valuation(product_code, target_date):
    """
    快照生成：使用T-1日净值
    """
    if not is_qdii(product_code):
        return query_price(product_code, target_date)
    
    # QDII：取前一交易日净值
    prev_date = prev_trading_day(target_date, 1)
    nav = query_price(product_code, prev_date)
    if not nav:
        raise ValueError(
            f"QDII产品{product_code}在T-1={prev_date}无净值数据"
        )
    return nav
```

### H. 权限控制矩阵

| 功能 | admin | viewer |
|------|-------|--------|
| 查看组合/持仓/收益 | ✅ | ✅（自己的） |
| 申购/赎回/调仓 | ✅ | ❌ |
| 管理投资人 | ✅ | ❌ |
| 管理产品/平台 | ✅ | ❌ |
| 系统设置/日志/任务 | ✅ | ❌ |
| 查看通知 | ✅（所有） | ✅（自己的） |

**Token 机制**：
- 格式：`{user_code}:{timestamp}:{signature}`（HMAC-SHA256）
- 有效期：7天
- 修改密码后原 token 失效
- 连续失败 5 次锁定账户 15 分钟

### I. LOF 拆分处理规则

同一LOF产品拆分为两条记录：
- `code=161725, market=CN_EXCHANGE` → 场内，confirm_days=0，使用 fund_daily 收盘价
- `code=161725, market=CN_OTC` → 场外，confirm_days=1，使用 fund_nav 净值

用户通过券商APP操作LOF时，需明确是"买卖"还是"申赎"，系统根据操作类型选择对应记录。

### J. 市场-数据源映射

| 市场 | 数据源 | 接口 | 字段 |
|------|--------|------|------|
| CN_EXCHANGE | tushare | fund_daily | unit_price（收盘价） |
| CN_OTC | tushare | fund_nav | unit_price（净值） |
| HK_MUTUAL | akshare | 基金接口 | unit_price（净值） |
| NULL | - | - | 无 |

**Tushare API 限流**：200次/分钟，单次返回量5000条，需实现限流器。
