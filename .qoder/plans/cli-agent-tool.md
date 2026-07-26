# InvestRing Admin CLI 工具实现计划

## Context

当前 InvestRing 的投资组合管理功能完全依赖 FastAPI HTTP 接口，AI agent 需要通过 HTTP 调用才能操作。为提高 AI agent 的自主操作效率，需要创建一个直接操作数据库的原生 CLI 工具，输出结构化 JSON，覆盖全部核心管理功能（主管理员版本）。

## 技术方案

- **框架**：Typer（基于 Click，支持类型注解）
- **架构**：直接 import backend 的 `database`/`services`/`models`，不经过 HTTP 层
- **安装**：通过 `pyproject.toml` 定义 entry point `ir`，`pip install -e .` 安装
- **输出**：所有输出为 JSON，统一 `{"ok": true/false, "data": ..., "meta": ...}` 格式
- **位置**：`backend/cli/` 目录

## 项目结构

```
backend/
├── pyproject.toml              # [新增] entry point + 元数据
├── cli/
│   ├── __init__.py
│   ├── main.py                 # Typer app 入口，注册 14 个命令组
│   ├── context.py              # DB session 管理、异常捕获、执行上下文
│   ├── output.py               # JSON 输出协议 + 自定义 JSONEncoder（Decimal/date/datetime）
│   ├── utils.py                # 公共辅助（模型序列化、日期解析）
│   └── commands/
│       ├── __init__.py
│       ├── auth.py             # ir auth create-admin
│       ├── investors.py        # ir investor list/create/get/update/delete
│       ├── portfolios.py       # ir portfolio list/create/get/update/close/reactivate/nav-history/returns/cash-flow
│       ├── positions.py        # ir position list/available-cash/available-shares/update-cash
│       ├── subscriptions.py    # ir sub list/create/get/confirm/cancel/unconfirm
│       ├── trades.py           # ir trade list/create/get/confirm/cancel/unconfirm
│       ├── share_events.py     # ir share-event list/create/get/update/delete/confirm/cancel
│       ├── market_data.py      # ir market price/sync/sync-history/sync-nav
│       ├── products.py         # ir product list/create/get/update/delete
│       ├── platforms.py        # ir platform list/create/get/update/delete
│       ├── system.py           # ir system calendar/calendar-sync/datasources/datasource-update
│       ├── logs.py             # ir log login/audit/error
│       ├── tasks.py            # ir task list/run/enable/disable/logs
│       └── snapshots.py        # ir snapshot generate/recalculate/validate/status/delete
├── app/
│   └── services/
│       ├── trading_utils.py    # [新增] 从 router 提取的公共函数
│       ├── position_service.py # [新增] 可用现金/份额计算
│       └── task_runner.py      # [新增] 任务执行体
└── requirements.txt            # [更新] 追加 typer
```

## 前置工作：提取共享业务函数

当前大量核心业务逻辑嵌入在 router 私有函数中（`_calculate_available_cash`、`_is_trading_day` 等），CLI 无法优雅复用。需先提取到 service 层：

### Task 1: 创建 `app/services/trading_utils.py`

从多个 router 中提取公共函数（这些函数在 subscriptions.py、trades.py、positions.py、share_change_events.py 中重复定义）：

| 函数 | 来源文件 |
|------|---------|
| `is_trading_day(db, target_date)` | routers/subscriptions.py:19, trades.py:111, share_change_events.py:21 |
| `get_next_trading_day(db, from_date, days)` | routers/subscriptions.py:216, trades.py:18 |
| `get_latest_snapshot_date(db, portfolio_code)` | routers/subscriptions.py:26, trades.py:118, positions.py:19 |

### Task 2: 创建 `app/services/position_service.py`

| 函数 | 来源文件 |
|------|---------|
| `calculate_available_cash(db, portfolio_code)` | routers/positions.py:28, trades.py:128 |
| `calculate_available_shares(db, portfolio_code, product_code, market)` | routers/positions.py:127, trades.py:220 |
| `calculate_investor_available_shares(db, investor_code, portfolio_code)` | routers/subscriptions.py:36 |

### Task 3: 创建 `app/services/task_runner.py`

从 `routers/tasks.py` 的 `run_task()` 函数中提取三个任务的执行体：
- `run_nav_sync(db)` — 净值同步 + 快照生成
- `run_calendar_sync(db, year)` — 交易日历同步
- `run_log_cleanup(db)` — 日志清理

### Task 4: 更新 router 引用

更新 `routers/subscriptions.py`、`routers/trades.py`、`routers/positions.py`、`routers/share_change_events.py`、`routers/tasks.py`，将原有的私有函数替换为从新 service 层 import。

## CLI 核心架构实现

### Task 5: 创建 `cli/output.py` — JSON 输出协议

- 自定义 `InvestRingEncoder(json.JSONEncoder)`：Decimal→float, date→ISO str, datetime→ISO str
- `success(data, meta=None)` — 输出 `{"ok": true, "data": ...}` + exit(0)
- `error(code, message, details=None)` — 输出 `{"ok": false, "error": ...}` + exit(1)
- 分页 meta：`{"total", "page", "page_size"}`

### Task 6: 创建 `cli/context.py` — 执行上下文

- `cli_context()` 上下文管理器：创建 SessionLocal → try/except → commit/rollback → close
- 异常映射：ValueError→VALIDATION_ERROR, IntegrityError→ALREADY_EXISTS, 其他→INTERNAL_ERROR

### Task 7: 创建 `cli/utils.py` — 辅助函数

- `serialize_model(obj, fields)` — SQLAlchemy model → dict
- 分页参数处理、日期解析

### Task 8: 创建 `cli/main.py` — 入口

- Typer app 实例，注册 14 个命令组
- `pyproject.toml` entry point 配置

## 命令实现（按优先级排序）

### Task 9: `ir auth` — 认证（1 条命令）

| 命令 | 说明 |
|------|------|
| `ir auth create-admin --code --name --password` | 创建管理员，使用 `get_password_hash()` |

### Task 10: `ir investor` — 投资人管理（5 条命令）

| 命令 | 说明 |
|------|------|
| `ir investor list [--page --page-size --all]` | 分页列表 |
| `ir investor create --code --name --password [--phone --email]` | 创建，默认 role=viewer |
| `ir investor get CODE` | 详情 |
| `ir investor update CODE [--name --role --phone --email --password]` | 更新 |
| `ir investor delete CODE [--yes]` | 删除（校验 InvestorHolding shares > 0 拒绝） |

### Task 11: `ir portfolio` — 组合管理（9 条命令）

| 命令 | 说明 |
|------|------|
| `ir portfolio list [--status --page --page-size]` | 列表 |
| `ir portfolio create --code --name [--description]` | 创建，status=draft |
| `ir portfolio get CODE` | 详情 |
| `ir portfolio update CODE [--name --description]` | 更新 |
| `ir portfolio close CODE [--yes]` | 关闭（校验无 pending 交易/申赎） |
| `ir portfolio reactivate CODE` | 重新激活 |
| `ir portfolio nav-history CODE [--start-date --end-date]` | 净值历史 |
| `ir portfolio returns CODE` | 收益率（累计+年化） |
| `ir portfolio cash-flow CODE` | 资金流 |

### Task 12: `ir product` — 产品管理（5 条命令）

| 命令 | 说明 |
|------|------|
| `ir product list [--product-type --page --page-size]` | 列表 |
| `ir product create --code --market --name --product-type [--asset-class-code --is-qdii]` | 创建，自动算 confirm_days |
| `ir product get CODE MARKET` | 详情（复合主键） |
| `ir product update CODE MARKET [--name --is-qdii ...]` | 更新 |
| `ir product delete CODE MARKET [--yes]` | 删除 |

### Task 13: `ir platform` — 平台管理（5 条命令）

| 命令 | 说明 |
|------|------|
| `ir platform list/get/create/update/delete` | 标准 CRUD |

### Task 14: `ir sub` — 申购赎回（6 条命令）

| 命令 | 说明 |
|------|------|
| `ir sub list [--portfolio-code --investor-code]` | 列表 |
| `ir sub create --portfolio-code --investor-code --type {subscribe,redeem} --amount/--shares --apply-date` | 创建 |
| `ir sub get ID` | 详情 |
| `ir sub confirm ID [--confirm-date --unit-price]` | 确认（首次申购净值1.0000，自动激活组合） |
| `ir sub cancel ID` | 取消 |
| `ir sub unconfirm ID` | 取消确认 |

业务逻辑参照 `routers/subscriptions.py`，使用 `trading_utils` + `position_service`。

### Task 15: `ir trade` — 调仓交易（6 条命令）

| 命令 | 说明 |
|------|------|
| `ir trade list [--portfolio-code]` | 列表 |
| `ir trade create --portfolio-code --product-code --market --type {buy,sell} --actual-amount --fee --platform-code --trade-date [--price --shares]` | 创建 |
| `ir trade get ID` | 详情 |
| `ir trade confirm ID [--confirm-date --price]` | 确认（自动获取净值，QDII 特殊处理） |
| `ir trade cancel ID` | 取消（仅 pending + 非场内） |
| `ir trade unconfirm ID` | 取消确认 |

### Task 16: `ir share-event` — 份额变动事件（7 条命令）

| 命令 | 说明 |
|------|------|
| `ir share-event list [--portfolio-code]` | 列表 |
| `ir share-event create --portfolio-code --product-code --market --event-type --event-date --entitlement-date ...` | 创建 |
| `ir share-event get/update/delete ID` | CRUD |
| `ir share-event confirm ID` | 确认（校验权益登记日持仓快照） |
| `ir share-event cancel ID` | 取消 |

### Task 17: `ir position` — 持仓管理（4 条命令）

| 命令 | 说明 |
|------|------|
| `ir position list --portfolio-code [--snapshot-date]` | 查看持仓（默认最新快照） |
| `ir position available-cash PORTFOLIO_CODE` | 可用现金（实时） |
| `ir position available-shares PORTFOLIO_CODE PRODUCT_CODE [--market]` | 可用份额（实时） |
| `ir position update-cash PORTFOLIO_CODE --platform-code --amount [--update-date]` | 更新现金 |

### Task 18: `ir market` — 市场数据（4 条命令）

直接调用 `MarketDataService`：

| 命令 | 说明 |
|------|------|
| `ir market price PRODUCT_CODE MARKET [--start-date --end-date --limit]` | 查询价格 |
| `ir market sync PRODUCT_CODE MARKET [--start-date --end-date]` | 同步价格（Tushare） |
| `ir market sync-history PRODUCT_CODE MARKET` | 同步 90 天历史 |
| `ir market sync-nav PORTFOLIO_CODE` | 同步组合净值 |

### Task 19: `ir snapshot` — 快照管理（5 条命令）

直接调用 `SnapshotService`：

| 命令 | 说明 |
|------|------|
| `ir snapshot generate --portfolio-code --target-date` | 生成单日快照 |
| `ir snapshot recalculate [--portfolio-code] --start-date --end-date [--force]` | 区间重算 |
| `ir snapshot validate --portfolio-code --target-date` | 校验依赖 |
| `ir snapshot status PORTFOLIO_CODE` | 快照状态 |
| `ir snapshot delete PORTFOLIO_CODE SNAPSHOT_DATE [--yes]` | 删除 |

### Task 20: `ir system` — 系统管理（4 条命令）

| 命令 | 说明 |
|------|------|
| `ir system calendar [--year --start-date --end-date --is-open]` | 查询交易日历 |
| `ir system calendar-sync --year` | 同步交易日历（Tushare） |
| `ir system datasources` | 查看数据源配置（key 脱敏） |
| `ir system datasource-update NAME [--api-key --is-enabled]` | 更新数据源 |

### Task 21: `ir log` — 日志管理（3 条命令）

| 命令 | 说明 |
|------|------|
| `ir log login [--page --page-size]` | 登录日志 |
| `ir log audit [--page --page-size]` | 审计日志 |
| `ir log error [--page --page-size]` | 错误日志 |

### Task 22: `ir task` — 任务管理（5 条命令）

调用 `task_runner.py` 提取的执行体：

| 命令 | 说明 |
|------|------|
| `ir task list` | 任务列表 |
| `ir task run CODE` | 手动执行（nav_sync/trading_calendar_sync/log_cleanup） |
| `ir task enable CODE` | 启用 |
| `ir task disable CODE` | 禁用 |
| `ir task logs CODE [--page --page-size]` | 执行日志 |

## 安装配置

### Task 23: 更新依赖和配置文件

- `requirements.txt` 追加 `typer>=0.9.0`
- 创建 `backend/pyproject.toml`：

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "investring"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
ir = "cli.main:app"

[tool.setuptools.packages.find]
include = ["cli*", "app*"]
```

- 安装：`cd backend && pip install -e .`

## 关键技术细节

1. **DB session**：每个命令创建一个 SessionLocal()，命令结束 commit+close，异常 rollback+close
2. **Decimal 处理**：输入 float → 内部 Decimal 运算 → 输出 float（round 4位）
3. **日期参数**：Typer 原生支持 `datetime.date` 注解，自动解析 YYYY-MM-DD
4. **lru_cache**：`get_settings()` 有缓存，`datasource-update` 修改 .env 后需 `get_settings.cache_clear()`
5. **PriceRecord 列名 bug**：model 定义为 `date`，但 snapshot_service 和 trades router 使用 `price_date` — 在 CLI 开发前需先修复此问题

## 验证方案

1. **安装验证**：`pip install -e .` 后 `ir --help` 正常显示命令列表
2. **数据库连接**：`ir investor list` 能正确返回数据
3. **业务流程测试**：使用 SQLite 测试数据库执行完整流程
   - `ir auth create-admin` → `ir investor create` → `ir portfolio create`
   - `ir sub create --type subscribe` → `ir sub confirm`
   - `ir trade create --type buy` → `ir trade confirm`
   - `ir snapshot generate`
4. **JSON 输出验证**：所有命令输出有效 JSON，可用 `jq` 解析
5. **错误处理验证**：`ir portfolio get NONEXIST` 返回错误 JSON + exit code 1
6. **现有测试**：`cd backend && pytest tests/` 确保 router 引用重构不影响现有功能

## 修改的关键文件清单

| 文件 | 操作 |
|------|------|
| `backend/pyproject.toml` | 新增 |
| `backend/cli/__init__.py` | 新增 |
| `backend/cli/main.py` | 新增 |
| `backend/cli/context.py` | 新增 |
| `backend/cli/output.py` | 新增 |
| `backend/cli/utils.py` | 新增 |
| `backend/cli/commands/*.py` (14个) | 新增 |
| `backend/app/services/trading_utils.py` | 新增 |
| `backend/app/services/position_service.py` | 新增 |
| `backend/app/services/task_runner.py` | 新增 |
| `backend/requirements.txt` | 更新（追加 typer） |
| `backend/app/routers/subscriptions.py` | 更新（import 改为 service 层） |
| `backend/app/routers/trades.py` | 更新（import 改为 service 层） |
| `backend/app/routers/positions.py` | 更新（import 改为 service 层） |
| `backend/app/routers/share_change_events.py` | 更新（import 改为 service 层） |
| `backend/app/routers/tasks.py` | 更新（import 改为 service 层） |
| `backend/app/services/snapshot_service.py` | 更新（修复 price_date→date） |
