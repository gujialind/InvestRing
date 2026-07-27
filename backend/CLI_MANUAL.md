# InvestRing Admin CLI 使用说明书

## 1. 概述

`ir` 是 InvestRing 的 AI Agent 原生命令行工具，直接操作后端数据库服务层（不经过 HTTP 接口），所有输出为结构化 JSON，适合 AI agent 和脚本自动化调用。

**版本**：主管理员版（覆盖全部管理功能，不含普通投资者查询接口）

## 2. 安装与环境

### 2.1 安装

```bash
cd backend
uv pip install --python ../.venv/bin/python -e .
```

安装后 `ir` 命令注册到虚拟环境的 `bin/` 目录下。

### 2.2 运行方式

```bash
# 方式一：通过虚拟环境路径直接调用
/home/collyn/projects/InvestRing/.venv/bin/ir <command>

# 方式二：激活虚拟环境后使用
source /home/collyn/projects/InvestRing/.venv/bin/activate
ir <command>

# 方式三：开发模式（不安装，通过 PYTHONPATH 运行）
cd backend
PYTHONPATH=. /home/collyn/projects/InvestRing/.venv/bin/python -m typer cli.main run <command>
```

### 2.3 运行前提

- 必须在 `backend/` 目录下运行（CLI 依赖 `backend/.env` 中的数据库连接配置）
- 虚拟环境中需安装：`typer`、`pymysql`、`sqlalchemy` 等依赖
- `.env` 文件中需正确配置 `DB_HOST`、`DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME`

### 2.4 获取帮助

```bash
ir --help                    # 查看所有命令组
ir portfolio --help          # 查看命令组下的子命令
ir portfolio create --help   # 查看具体命令的参数帮助
```

## 3. 输出格式

### 3.1 成功响应（exit code 0）

```json
{
  "ok": true,
  "data": { ... },
  "meta": { "total": 100, "page": 1, "page_size": 20 }
}
```

- `data`：主要数据，可以是对象或数组
- `meta`：分页元数据（仅列表命令返回），包含 `total`（总数）、`page`（当前页）、`page_size`（每页大小）

### 3.2 错误响应（exit code 1）

```json
{
  "ok": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "组合 PORT999 不存在"
  }
}
```

### 3.3 错误码一览

| 错误码 | 说明 |
|--------|------|
| `NOT_FOUND` | 资源不存在 |
| `ALREADY_EXISTS` | 资源已存在（唯一约束冲突） |
| `VALIDATION_ERROR` | 参数校验失败 |
| `INVALID_STATUS` | 状态不允许当前操作 |
| `INVALID_AMOUNT` / `INVALID_SHARES` | 金额/份额不合法 |
| `INSUFFICIENT_CASH` | 买入金额超过可用现金 |
| `INSUFFICIENT_SHARES` | 卖出/赎回份额超过可用份额 |
| `NON_TRADING_DAY` | 提交日期不是交易日 |
| `MISSING_NAV` | 确认时缺少净值数据 |
| `PENDING_TRANSACTIONS_EXIST` | 存在未处理的交易 |
| `PORTFOLIO_NOT_ACTIVE` | 组合未激活 |
| `INVESTOR_HAS_SHARES` | 投资人仍持有份额，不可删除 |
| `DATA_SOURCE_ERROR` | 外部数据源同步失败 |
| `INTERNAL_ERROR` | 系统内部错误 |

### 3.4 数据类型说明

- **日期参数**：所有日期参数使用 `YYYY-MM-DD` 格式字符串，如 `--apply-date 2025-01-06`
- **金额/份额**：使用浮点数输入，内部以 Decimal 运算，输出保留 4 位小数
- **ID 参数**：数值型主键，直接作为位置参数传入

### 3.5 AI Agent 友好特性（仅 ir-cli HTTP 版）

以下特性仅在 `ir-cli`（HTTP 客户端版）提供，用于降低 AI agent 的学习成本与 token 消耗：

- **`ir schema [命令组]`**：一次性输出全 CLI 机读 JSON 结构，含命令树/参数/枚举取值/错误码补救指引/端到端业务配方（workflows）/输出协议，替代逐个 `--help` 探索；传命令组名（如 `ir schema trade`）仅输出单组。
- **`ir portfolio context <code>`**：操作前侦察聚合命令，一次返回组合详情/快照状态/实时可用现金/pending 申赎交易，替代 4-5 次分步查询。
- **`hints` 字段**：错误响应按错误码自动附加 `error.hints`（下一步补救命令，如 `SNAPSHOT_DEPENDENCY` → 先 `ir snapshot delete-bulk`）；关键写操作成功后输出顶层 `hints`（如 create 返回 pending 时提示 confirm、confirm 后提示生成快照）。映射表见 `ir_cli/hints.py`。
- **摘要字段默认输出**：`trade list` / `sub list` / `position list` / `log login|audit|error` 默认仅输出摘要字段（见 `ir_cli/utils.py::SUMMARY_FIELDS`），`--full` 输出全字段；优先级：显式 `--fields` > `--full` > 摘要预设。
- **`--quiet`**：`trade` / `sub` 的 create/confirm/cancel/unconfirm 仅输出 `{id, status, confirm_date}`。
- **plain help**：全部 `--help` 为无框线/无 ANSI 的纯文本输出，顶层 `ir --help` 含输出协议与退出码速览。

## 4. 命令详解

---

### 4.1 `ir auth` — 认证管理

#### `ir auth create-admin`

创建管理员账户。

```bash
ir auth create-admin --code <管理员代码> --name <姓名> --password <密码>
```

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--code` | 是 | 管理员代码（唯一标识） |
| `--name` | 是 | 管理员姓名 |
| `--password` | 是 | 登录密码（存储时自动哈希） |

**示例：**
```bash
ir auth create-admin --code ADMIN --name "系统管理员" --password "secure123"
```

---

### 4.2 `ir investor` — 投资人管理

#### `ir investor list`

获取投资人列表（分页）。

```bash
ir investor list [--page N] [--page-size N] [--all]
```

| 参数 | 默认值 | 说明 |
|------|:------:|------|
| `--page` | 1 | 页码 |
| `--page-size` | 20 | 每页数量 |
| `--all` | false | 获取全部记录 |

#### `ir investor create`

创建投资人。

```bash
ir investor create --code <代码> --name <姓名> --password <密码> [--phone <手机>] [--email <邮箱>] [--role <角色>]
```

| 参数 | 必填 | 默认值 | 说明 |
|------|:----:|:------:|------|
| `--code` | 是 | — | 投资人代码（唯一标识） |
| `--name` | 是 | — | 投资人姓名 |
| `--password` | 是 | — | 登录密码 |
| `--phone` | 否 | — | 手机号 |
| `--email` | 否 | — | 邮箱 |
| `--role` | 否 | viewer | 角色：`admin` / `viewer` |

#### `ir investor get`

查看投资人详情。

```bash
ir investor get <CODE>
```

#### `ir investor update`

更新投资人信息。

```bash
ir investor update <CODE> [--name <姓名>] [--role <角色>] [--phone <手机>] [--email <邮箱>] [--password <新密码>]
```

所有选项参数均可选，仅更新传入的字段。

#### `ir investor delete`

删除投资人。

```bash
ir investor delete <CODE> [--yes]
```

| 参数 | 默认值 | 说明 |
|------|:------:|------|
| `--yes` | false | 跳过确认提示 |

> **约束**：投资人仍持有份额（`InvestorHolding.shares > 0`）时禁止删除。

---

### 4.3 `ir portfolio` — 组合管理

#### `ir portfolio list`

获取组合列表。

```bash
ir portfolio list [--status <状态>] [--page N] [--page-size N] [--all]
```

| 参数 | 默认值 | 说明 |
|------|:------:|------|
| `--status` | — | 按状态过滤：`draft` / `active` / `closed` |
| `--page` | 1 | 页码 |
| `--page-size` | 20 | 每页数量 |
| `--all` | false | 获取全部 |

#### `ir portfolio create`

创建组合（初始状态为 `draft`）。

```bash
ir portfolio create --code <代码> --name <名称> [--description <描述>]
```

#### `ir portfolio get`

查看组合详情。

```bash
ir portfolio get <CODE>
```

#### `ir portfolio update`

更新组合信息。

```bash
ir portfolio update <CODE> [--name <名称>] [--description <描述>]
```

#### `ir portfolio close`

关闭组合。

```bash
ir portfolio close <CODE> [--yes]
```

> **约束**：存在 pending 状态的申购/赎回或调仓交易时禁止关闭。

#### `ir portfolio reactivate`

重新激活已关闭的组合。

```bash
ir portfolio reactivate <CODE>
```

> **约束**：仅 `closed` 状态可激活。

#### `ir portfolio nav-history`

查看组合净值历史。

```bash
ir portfolio nav-history <CODE> [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
```

返回单层数组，每行包含：`snapshot_date`、`unit_price`（单位净值）、`total_value`（总资产）、`total_shares`（总份额），按日期升序。

```json
{
  "ok": true,
  "data": [
    {"snapshot_date": "2025-01-06", "unit_price": 1.0, "total_value": 100000.0, "total_shares": 100000.0},
    {"snapshot_date": "2025-01-07", "unit_price": 1.01, "total_value": 101000.0, "total_shares": 100000.0}
  ]
}
```

#### `ir portfolio returns`

查看组合收益率。

```bash
ir portfolio returns <CODE>
```

返回数据包含：`cumulative_return`（累计收益率 %）、`annualized_return`（年化收益率 %）、`initial_nav`、`current_nav`、`holding_days`。

> **前提**：需要至少 2 条快照记录。

#### `ir portfolio cash-flow`

查看组合资金流。

```bash
ir portfolio cash-flow <CODE>
```

返回数据包含：`total_inflow`（总申购金额）、`total_outflow`（总赎回金额）、`net_inflow`（净流入）。

---

### 4.4 `ir position` — 持仓管理

#### `ir position list`

查看持仓（默认取每只产品的最新快照）。

```bash
ir position list --portfolio-code <组合代码> [--snapshot-date YYYY-MM-DD] [--page N] [--page-size N]
```

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--portfolio-code` | 是 | 组合代码 |
| `--snapshot-date` | 否 | 指定快照日期，不传则取最新 |

#### `ir position available-cash`

查看组合可用现金（实时计算，非快照数据）。

```bash
ir position available-cash <PORTFOLIO_CODE>
```

#### `ir position available-shares`

查看产品可用份额（实时计算）。

```bash
ir position available-shares <PORTFOLIO_CODE> <PRODUCT_CODE> [--market <市场>]
```

#### `ir position update-cash`

更新非净值类现金市值：写入 `manual_market_value`（绝对替换），**不直接写快照表 `portfolio_position`**；写入后需重新生成快照方能反映到持仓（响应含 `requires_snapshot_regen: true`）。与 REST `POST /api/positions/portfolio/{code}/cash-position` 共用同一 service。

```bash
ir position update-cash <PORTFOLIO_CODE> --platform-code <平台代码> --amount <金额> [--update-date YYYY-MM-DD]
```

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--platform-code` | 是 | 所属平台代码 |
| `--amount` | 是 | 现金金额（绝对值，覆盖当日该平台现金市值） |
| `--update-date` | 否 | 更新日期（默认今天，必须是交易日） |

---

### 4.5 `ir sub` — 申购赎回管理

#### `ir sub list`

获取申购赎回列表。

```bash
ir sub list [--portfolio-code <组合>] [--investor-code <投资人>] [--page N] [--page-size N] [--all]
```

#### `ir sub create`

创建申购或赎回。

```bash
# 申购（按金额）
ir sub create --portfolio-code <组合> --investor-code <投资人> --type subscribe --amount <金额> --apply-date YYYY-MM-DD [--notes <备注>]

# 赎回（按份额）
ir sub create --portfolio-code <组合> --investor-code <投资人> --type redeem --shares <份额> --apply-date YYYY-MM-DD [--notes <备注>]
```

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--portfolio-code` | 是 | 组合代码 |
| `--investor-code` | 是 | 投资人代码 |
| `--type` | 是 | `subscribe`（申购）或 `redeem`（赎回） |
| `--amount` | 申购时必填 | 申购金额（必须 > 0） |
| `--shares` | 赎回时必填 | 赎回份额（必须 > 0，不可超过可用份额） |
| `--apply-date` | 是 | 申请日期（必须是交易日） |
| `--notes` | 否 | 备注 |

> **业务规则**：
> - 申请日期必须是交易日
> - 组合状态必须为 `active` 或 `draft`
> - 赎回份额不可超过投资人可用份额

#### `ir sub get`

查看申购赎回详情。

```bash
ir sub get <ID>
```

#### `ir sub confirm`

确认申购赎回。

```bash
ir sub confirm <ID> [--confirm-date YYYY-MM-DD] [--unit-price <净值>]
```

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--confirm-date` | 否 | 确认日期（默认自动计算下一交易日） |
| `--unit-price` | 视情况 | 确认净值 |

> **业务规则**：
> - 仅 `pending` 状态可确认
> - **首次申购**：净值固定为 `1.0000`，无需提供 `--unit-price`，同时自动将组合从 `draft` 激活为 `active`
> - **非首次申购/赎回**：必须提供 `--unit-price`

#### `ir sub cancel`

取消申购赎回（仅 `pending` 状态可操作）。

```bash
ir sub cancel <ID>
```

#### `ir sub unconfirm`

取消确认，将 `confirmed` 状态回退为 `pending`。

```bash
ir sub unconfirm <ID>
```

---

### 4.6 `ir trade` — 调仓交易管理

#### `ir trade list`

获取调仓交易列表。

```bash
ir trade list [--portfolio-code <组合>] [--page N] [--page-size N] [--all]
```

#### `ir trade create`

创建买入/卖出交易。

```bash
# 买入
ir trade create --portfolio-code <组合> --product-code <产品> --market <市场> \
  --type buy --actual-amount <实际金额> --fee <手续费> --price <价格> \
  --trade-date YYYY-MM-DD [--platform-code <平台>] [--shares <份额>] [--notes <备注>]

# 卖出
ir trade create --portfolio-code <组合> --product-code <产品> --market <市场> \
  --type sell --shares <份额> --trade-date YYYY-MM-DD [--actual-amount <实际金额>] \
  [--fee <手续费>] [--platform-code <平台>] [--notes <备注>]
```

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--portfolio-code` | 是 | 组合代码（必须为 `active` 状态） |
| `--product-code` | 是 | 产品代码 |
| `--market` | 是 | 市场类型：`CN_OTC` / `CN_EXCHANGE` / `HK_MUTUAL` |
| `--type` | 是 | `buy`（买入）或 `sell`（卖出） |
| `--actual-amount` | 买入时必填 | 实际支付金额（必须 > 0，不超过可用现金） |
| `--fee` | 否（默认0） | 手续费 |
| `--price` | 否 | 交易价格 |
| `--shares` | 卖出时必填 | 卖出份额（必须 > 0，不超过可用份额） |
| `--platform-code` | 否 | 平台代码 |
| `--trade-date` | 是 | 交易日期（必须是交易日） |
| `--notes` | 否 | 备注 |

#### `ir trade get`

查看交易详情。

```bash
ir trade get <ID>
```

#### `ir trade confirm`

确认交易（自动获取净值，QDII 产品特殊处理）。

```bash
ir trade confirm <ID> [--confirm-date YYYY-MM-DD] [--price <价格>]
```

> **业务规则**：
> - 仅 `pending` 状态可确认
> - 确认日期根据产品的 `confirm_days` 自动计算（普通基金 T+1，QDII T+2）
> - 场外净值类产品（OEF/LOF + CN_OTC）自动从 `PriceRecord` 获取净值
> - **QDII 产品**：使用交易日当天的净值（需 T+2 日后确认）
> - 可通过 `--price` 手动覆盖价格

#### `ir trade cancel`

取消交易。

```bash
ir trade cancel <ID>
```

> **约束**：仅 `pending` 状态且非场内交易（`CN_EXCHANGE`）可取消。

#### `ir trade unconfirm`

取消确认，将 `confirmed` 状态回退为 `pending`。

```bash
ir trade unconfirm <ID>
```

---

### 4.7 `ir share-event` — 份额变动事件管理

管理分红、再投资、拆合股等份额变动事件。

#### `ir share-event list`

获取事件列表。

```bash
ir share-event list [--portfolio-code <组合>] [--page N] [--page-size N] [--all]
```

#### `ir share-event create`

创建份额变动事件。

```bash
ir share-event create \
  --portfolio-code <组合> --product-code <产品> --market <市场> \
  --event-type <事件类型> \
  --ex-date YYYY-MM-DD --entitlement-date YYYY-MM-DD \
  [--platform-code <平台>] \
  [--entitlement-shares N] [--shares-before N] [--shares-change N] [--shares-after N] \
  [--ratio N] [--div-cash N] [--reinvest-nav N] [--cash-change N] \
  [--event-source <来源>] [--notes <备注>] [--force-cover]
```

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--portfolio-code` | 是 | 组合代码 |
| `--product-code` | 是 | 产品代码 |
| `--market` | 是 | 市场类型 |
| `--event-type` | 是 | 事件类型（见下表） |
| `--ex-date` | 是 | 除息日/应用日（**必须是交易日**，且 > 权益登记日） |
| `--entitlement-date` | 是 | 权益登记日（基数日，**必须是交易日**） |
| `--platform-code` | 视类型 | 平台级事件（cash_dividend/reinvest_dividend/forced_adjustment）必填 |
| `--entitlement-shares` | 否 | 权益登记日份额 |
| `--shares-before` | 否 | 变动前份额 |
| `--shares-change` | 否 | 变动份额 |
| `--shares-after` | 否 | 变动后份额 |
| `--ratio` | 否 | 比例（拆合股用） |
| `--div-cash` | 否 | 现金分红金额 |
| `--reinvest-nav` | 否 | 再投资净值 |
| `--cash-change` | 否 | 现金变动 |
| `--event-source` | 否 | 事件来源 |
| `--notes` | 否 | 备注 |
| `--force-cover` | 否 | 平台覆盖不全时降为 warning（默认阻断） |

**事件类型：**

| 类型 | 说明 |
|------|------|
| `cash_dividend` | 现金分红 |
| `reinvest_dividend` | 红利再投资 |
| `share_split` | 份额拆分 |
| `share_merge` | 份额合并 |
| `bonus_share` | 送股 |
| `forced_adjustment` | 强制调整 |

#### `ir share-event get`

查看事件详情。

```bash
ir share-event get <ID>
```

#### `ir share-event update`

更新事件信息。

```bash
ir share-event update <ID> [--ex-date YYYY-MM-DD] [--entitlement-shares N] [--ratio N] \
  [--div-cash N] [--reinvest-nav N] [--cash-change N] [--notes <备注>]
```

#### `ir share-event delete`

删除事件。

```bash
ir share-event delete <ID> [--yes]
```

#### `ir share-event confirm`

确认事件（校验权益登记日持仓快照存在）。

```bash
ir share-event confirm <ID>
```

> **约束**：仅 `pending` 状态可确认，且权益登记日必须有持仓快照。

#### `ir share-event cancel`

取消事件（仅 `pending` 状态可操作）。

```bash
ir share-event cancel <ID>
```

#### `ir share-event unconfirm`

取消确认事件（`confirmed` → `pending`）。

```bash
ir share-event unconfirm <ID>
```

> **约束**：仅 `confirmed` 状态可取消确认；`ex_date` 及之后已有快照则返回 `SNAPSHOT_DEPENDENCY`（需先删除对应快照）。基金级父记录会级联删除其拆分子记录后置 `pending`；子记录单独 unconfirm 会被拒绝（`CANNOT_UNCONFIRM_CHILD`）。

---

### 4.8 `ir market` — 市场数据

#### `ir market price`

查询产品价格数据。

```bash
ir market price <PRODUCT_CODE> <MARKET> [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--limit N]
```

| 参数 | 默认值 | 说明 |
|------|:------:|------|
| `--start-date` | — | 起始日期 |
| `--end-date` | — | 截止日期 |
| `--limit` | 50 | 最大返回条数（按日期降序） |

#### `ir market nav-coverage`

校验区间内净值同步覆盖情况（以交易日历为基准，列出缺失日期）。

```bash
ir market nav-coverage <PRODUCT_CODE> <MARKET> --start-date YYYY-MM-DD [--end-date YYYY-MM-DD]
```

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--start-date` | 是 | 开始日期 |
| `--end-date` | 否 | 结束日期，默认今天 |

返回示例：

```json
{
  "ok": true,
  "data": {
    "product_code": "000300.OF",
    "market": "CN_OTC",
    "start_date": "2025-01-06",
    "end_date": "2025-01-10",
    "total_trading_days": 5,
    "synced_days": 4,
    "coverage": 0.8,
    "missing_dates": ["2025-01-08"]
  }
}
```

> `coverage` = `synced_days / total_trading_days`；区间内无交易日时为 `null`。

#### `ir market sync`

从 Tushare 同步产品价格数据。

```bash
ir market sync <PRODUCT_CODE> <MARKET> [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
```

#### `ir market sync-history`

同步产品近 90 天历史数据（自动计算日期范围）。

```bash
ir market sync-history <PRODUCT_CODE> <MARKET>
```

---

### 4.9 `ir product` — 产品管理

#### `ir product list`

获取产品列表。

```bash
ir product list [--product-type <类型>] [--page N] [--page-size N] [--all]
```

| 参数 | 说明 |
|------|------|
| `--product-type` | 按类型过滤：`ETF` / `OEF` / `LOF` / `CASH` |

#### `ir product create`

创建产品（自动根据市场类型和 QDII 属性计算 `confirm_days`）。

```bash
ir product create --code <代码> --market <市场> --name <名称> --product-type <类型> \
  [--asset-class-code <资产类别>] [--is-qdii] [--data-source <数据源>]
```

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--code` | 是 | 产品代码（如 `000051.OF`） |
| `--market` | 是 | 市场：`CN_EXCHANGE` / `CN_OTC` / `HK_MUTUAL` |
| `--name` | 是 | 产品名称 |
| `--product-type` | 是 | 类型：`ETF` / `OEF` / `LOF` / `CASH` |
| `--asset-class-code` | 否 | 资产类别代码 |
| `--is-qdii` | 否 | 是否为 QDII 产品（默认 false） |
| `--data-source` | 否 | 数据源（如 `tushare`） |

**confirm_days 自动计算规则：**

| 市场 | QDII | confirm_days |
|------|:----:|:------------:|
| `CN_EXCHANGE` | — | 0 |
| `CN_OTC` | 否 | 1 |
| `CN_OTC` | 是 | 2 |
| 其他 | — | 0 |

#### `ir product get`

查看产品详情（复合主键：代码 + 市场）。

```bash
ir product get <CODE> <MARKET>
```

#### `ir product update`

更新产品信息。

```bash
ir product update <CODE> <MARKET> [--name <名称>] [--is-qdii true/false] \
  [--asset-class-code <类别>] [--data-source <数据源>]
```

> 更新 `--is-qdii` 时会自动重新计算 `confirm_days`。

#### `ir product delete`

删除产品。

```bash
ir product delete <CODE> <MARKET> [--yes]
```

---

### 4.10 `ir platform` — 平台管理

#### `ir platform list`

获取平台列表。

```bash
ir platform list [--page N] [--page-size N] [--all]
```

#### `ir platform create`

创建平台。

```bash
ir platform create --code <代码> --name <名称> [--platform-type <类型>]
```

#### `ir platform get`

查看平台详情。

```bash
ir platform get <CODE>
```

#### `ir platform update`

更新平台信息。

```bash
ir platform update <CODE> [--name <名称>] [--platform-type <类型>]
```

#### `ir platform delete`

删除平台。

```bash
ir platform delete <CODE> [--yes]
```

---

### 4.11 `ir snapshot` — 快照管理

#### `ir snapshot generate`

生成单日快照。

```bash
ir snapshot generate --portfolio-code <组合> --target-date YYYY-MM-DD
```

#### `ir snapshot recalculate`

区间重算快照。

```bash
ir snapshot recalculate --start-date YYYY-MM-DD --end-date YYYY-MM-DD [--portfolio-code <组合>] [--force]
```

| 参数 | 说明 |
|------|------|
| `--portfolio-code` | 指定组合（不传则重算所有活跃组合） |
| `--start-date` | 起始日期（必填） |
| `--end-date` | 截止日期（必填） |
| `--force` | 跳过校验强制重算 |

#### `ir snapshot validate`

校验指定日期的快照依赖数据是否齐全。

```bash
ir snapshot validate --portfolio-code <组合> --target-date YYYY-MM-DD
```

返回 `is_valid`（是否有效）和 `checks`（各项检查详情）。

#### `ir snapshot status`

查看组合快照状态。

```bash
ir snapshot status <PORTFOLIO_CODE>
```

返回 `nav_snapshot_count`（快照总数）、`latest_date`（最新日期）、`earliest_date`（最早日期）。

#### `ir snapshot delete`

删除指定日期的快照（包括持仓快照、净值快照、投资人持仓三类数据）。

```bash
ir snapshot delete <PORTFOLIO_CODE> <SNAPSHOT_DATE> [--yes]
```

#### `ir snapshot delete-bulk`

批量删除从起始日期（含当日）起的所有快照，从最新快照日倒序逐日删除并级联回退。

```bash
ir snapshot delete-bulk <PORTFOLIO_CODE> <FROM_DATE> --yes
```

| 参数 | 默认值 | 说明 |
|------|:------:|------|
| `--yes` | false | 必传。不带 `--yes` 时拒绝执行（`CONFIRM_REQUIRED`） |

> **破坏性操作**：逐日 commit，不可中途回滚。对应的 REST 端点 `DELETE /api/v1/snapshots/{portfolio_code}/bulk/{from_date}` 同样要求显式传 `confirm=true`，否则返回 422 `CONFIRM_REQUIRED`（兼作影响面预览）。

---

### 4.12 `ir system` — 系统管理

#### `ir system calendar`

查询交易日历。

```bash
ir system calendar [--year N] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--is-open true/false]
```

| 参数 | 说明 |
|------|------|
| `--year` | 按年份查询 |
| `--start-date` | 起始日期 |
| `--end-date` | 截止日期 |
| `--is-open` | 按是否交易日过滤 |

#### `ir system calendar-sync`

从 Tushare 同步交易日历。

```bash
ir system calendar-sync --year <年份>
```

#### `ir system datasources`

查看数据源配置（API key 脱敏显示）。

```bash
ir system datasources
```

#### `ir system datasource-update`

更新数据源配置。

```bash
ir system datasource-update tushare --api-key <新的Tushare Token>
```

> 更新后自动刷新配置缓存。

---

### 4.13 `ir log` — 日志管理

#### `ir log login`

查询登录日志。

```bash
ir log login [--page N] [--page-size N]
```

#### `ir log audit`

查询审计日志。

```bash
ir log audit [--page N] [--page-size N]
```

#### `ir log error`

查询系统错误日志。

```bash
ir log error [--page N] [--page-size N]
```

---

### 4.14 `ir task` — 定时任务管理

#### `ir task list`

获取定时任务列表。

```bash
ir task list [--page N] [--page-size N]
```

#### `ir task run`

手动执行任务。

```bash
ir task run <CODE>
```

**支持的任务代码：**

| 任务代码 | 说明 |
|----------|------|
| `nav_sync` | 净值同步 + 快照生成 |
| `trading_calendar_sync` | 交易日历同步 |
| `log_cleanup` | 过期日志清理 |

#### `ir task enable`

启用任务。

```bash
ir task enable <CODE>
```

#### `ir task disable`

禁用任务。

```bash
ir task disable <CODE>
```

#### `ir task logs`

查看任务执行日志。

```bash
ir task logs <CODE> [--page N] [--page-size N]
```

---

## 5. 典型业务流程

### 5.1 从零开始创建组合并完成首笔交易

```bash
# 1. 创建管理员（首次使用）
ir auth create-admin --code ADMIN --name "管理员" --password "pass123"

# 2. 创建投资人
ir investor create --code INV001 --name "张三" --password "pass123"

# 3. 创建组合
ir portfolio create --code PORT001 --name "个人养老金"

# 4. 首次申购（净值固定 1.0000，组合自动激活为 active）
ir sub create --portfolio-code PORT001 --investor-code INV001 \
  --type subscribe --amount 100000 --apply-date 2025-01-06
# 记录返回的 ID，假设为 1

# 5. 确认申购
ir sub confirm 1

# 6. 查看可用现金
ir position available-cash PORT001

# 7. 创建买入交易
ir trade create --portfolio-code PORT001 --product-code 000051.OF --market CN_OTC \
  --type buy --actual-amount 50000 --fee 0 --price 1.5 --trade-date 2025-01-07

# 8. 确认交易
ir trade confirm 1

# 9. 生成快照
ir snapshot generate --portfolio-code PORT001 --target-date 2025-01-07

# 10. 查看组合净值和收益率
ir portfolio nav-history PORT001
ir portfolio returns PORT001
```

### 5.2 分红处理

```bash
# 1. 创建现金分红事件
ir share-event create --portfolio-code PORT001 --product-code 000051.OF --market CN_OTC \
  --event-type cash_dividend \
  --event-date 2025-06-15 --entitlement-date 2025-06-13 \
  --div-cash 500 --entitlement-shares 33333.3333

# 2. 生成权益登记日的快照（如果还没有）
ir snapshot generate --portfolio-code PORT001 --target-date 2025-06-13

# 3. 确认分红事件
ir share-event confirm 1
```

### 5.3 日常运维

```bash
# 同步交易日历
ir system calendar-sync --year 2025

# 手动执行净值同步任务
ir task run nav_sync

# 生成今日快照
ir snapshot generate --portfolio-code PORT001 --target-date $(date +%Y-%m-%d)

# 查看数据源配置
ir system datasources
```

## 6. AI Agent 集成指南

### 6.1 调用方式

AI agent 可通过 shell 命令直接调用，解析 JSON 输出获取结果：

```python
import subprocess, json

result = subprocess.run(
    ["/path/to/.venv/bin/ir", "portfolio", "list", "--status", "active"],
    capture_output=True, text=True, cwd="/path/to/backend"
)
data = json.loads(result.stdout)
if data["ok"]:
    portfolios = data["data"]
```

### 6.2 错误处理

通过 exit code 和 JSON 中的 `ok` 字段判断是否成功：

```bash
output=$(ir portfolio get PORT999 2>/dev/null)
exit_code=$?
if [ $exit_code -ne 0 ]; then
    error_code=$(echo "$output" | jq -r '.error.code')
    # 处理错误
fi
```

### 6.3 链式操作

利用 `jq` 提取数据进行链式操作：

```bash
# 获取所有活跃组合的代码
ir portfolio list --status active --all 2>/dev/null | jq -r '.data[].code'

# 遍历每个活跃组合生成快照
for code in $(ir portfolio list --status active --all 2>/dev/null | jq -r '.data[].code'); do
    ir snapshot generate --portfolio-code "$code" --target-date 2025-01-06
done
```

## 7. 注意事项

1. **交易日历依赖**：申购、赎回、交易、份额变动事件的日期必须是交易日。请先确保已通过 `ir system calendar-sync` 同步了当年的交易日历。

2. **净值数据依赖**：交易确认和快照生成依赖 `PriceRecord` 中的净值数据。请先通过 `ir market sync` 或 `ir market sync-history` 同步产品净值。

3. **快照顺序依赖**：快照按日逐日生成，某日快照依赖前一天的快照数据。区间重算（`ir snapshot recalculate`）可修复断裂的快照链。

4. **首次申购特殊规则**：组合的首次申购确认时净值固定为 `1.0000`，同时自动将组合状态从 `draft` 切换为 `active`。

5. **QDII 产品**：QDII 产品的净值延迟一天（T+2 确认），确认交易时需确保净值已同步。

6. **数据精度**：内部使用 Python `Decimal` 进行运算，输出时金额保留 2 位小数，份额和净值保留 4 位小数。

7. **运行目录**：建议在 `backend/` 目录下执行 CLI 命令，确保 `.env` 配置文件能被正确读取。
