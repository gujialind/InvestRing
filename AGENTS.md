# InvestRing 开发指南 (AGENTS.md)

> 为 AI 编程助手提供项目级快速参考。本文只记录**读代码发现不了**的内容：设计决策、业务不变量、组织约定与易踩坑；路由、枚举、错误码、表结构、版本号、确认天数等以源码为准（可发现性过滤，见 §8.5）。

***

## 1. 项目概览

**InvestRing** 是我设计的供自己使用的投资组合管理工具，本质是一个支持净值化，多投资人的记账系统，为个人和家庭财富管理、大类资产配置提供完整的数据体系，适用的持仓资产目前限于：公募基金（含场内ETF和场外基金），股票，现金。所有资产人民币计价，无汇率换算。

**Monorepo 布局**（技术栈版本明细以 `frontend/package.json` / `backend/pyproject.toml` 为准）：

| 目录                                        | 内容                                                                          |
| ----------------------------------------- | --------------------------------------------------------------------------- |
| `backend/`                                | FastAPI + SQLAlchemy 后端；含 `app/`（应用）、`alembic/`（迁移）、`tests/` |
| `frontend/`                               | Next.js 前端（App Router，双端路由，技术栈见 §5）                                   |
| `ir-cli/`                                 | 独立轻量 HTTP 客户端 CLI（typer + httpx）                                            |
| `nginx/`、`scripts/`、`docker-compose*.yml` | 部署与运维                                                                       |

**运行入口**：后端 `backend/app/main.py`（启动初始化行为读源码）；前端 `npm run dev`；`ir` CLI 的说明见 §6。

***

## 2. 核心领域模型与不变量

> 本章是所有业务规则的**单一事实来源**，其他章节只引用不重复。

### 2.1 快照三表与生成

**三张快照表，只增不改**：`portfolio_position`（持仓）、`portfolio_value_snapshot`（组合市值）、`investor_holding`（投资人份额）。

* 快照每天汇总生成一次（不是每笔交易生成），永不 UPDATE，保留完整历史（ORM 层 `before_update`/`before_delete` 事件兜底禁止实例级改删）。
* **固定生成顺序**：`portfolio_position` → `portfolio_value_snapshot` → `investor_holding`。
* **生成前提**：`confirm_date <= snapshot_date` 的申赎/交易/事件均已确认，不存在会影响该日的 pending 记录（存在 `ex_date <= target_date` 的 pending 事件时快照检查返回 failed）。查询当前状态用 `WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM ...)`。
* **快照连续原则**：快照有前后依赖，必须严格按交易日顺序连续生成（从最新快照日的下一个交易日起），失败即停、不允许跳过。单日生成入口（`generate_daily_snapshots`）强制校验：目标日仅允许为最新快照日（重建最新一日）或其下一个交易日，否则返回 `SNAPSHOT_NOT_CONTINUOUS`（重算路径逐日重建时内部 bypass）。

### 2.2 现金显式流水

所有现金变动**显式记录**，不再从申赎/调仓隐式反推。三类现金影响源：

| 来源           | 记录表                    | 关联方式                                                                                                                       |
| ------------ | ---------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| 交易（申赎/调仓/转移） | `trade`（CASH buy/sell） | `transfer_group` 关联同组记录                                                                                                    |
| 事件（现金分红等）    | `share_change_event`   | `cash_change` 字段，按 `ex_date` 生效                                                                                            |
| 手动重估         | `manual_market_value`  | 按日期绝对替换，不进 trade / event；优先级高于当日全部交易/事件，且作为后续快照增量基线；可删除（DELETE cash-position / `ir position delete-cash`），删除后需重算快照才回退自然计算值 |

各业务操作生成的 CASH trade：

| 操作    | CASH trade                  | transfer\_group         |
| ----- | --------------------------- | ----------------------- |
| 申购确认  | 1 条 CASH buy（直接 confirmed）  | `sub_{subscription.id}` |
| 赎回确认  | 1 条 CASH sell（直接 confirmed） | `sub_{subscription.id}` |
| 基金买入  | 基金 buy + CASH sell（同状态/日期）  | `rebal_{uuid}`          |
| 基金卖出  | 基金 sell + CASH buy（同状态/日期）  | `rebal_{uuid}`          |
| 跨平台转移 | CASH sell + CASH buy        | `{uuid}`（12 位 hex）      |

* **跨平台现金腿**（#91）：基金买/卖可传 `cash_platform_code`（买=扣款平台、卖=到账平台，CLI `--cash-platform-code`），CASH 腿落在指定平台、缺省同基金腿；买入可用现金按扣款平台校验（创建与确认均是），两腿仍同 transfer\_group 原子翻转，免去前置平台间现金转移。

**两条计算口径**（`position_service.py`）：

```
compute_cash_balance(T) = SUM(confirmed CASH trades WHERE confirm_date <= T)
                        + SUM(confirmed events WHERE ex_date <= T, cash_change != 0)

calculate_available_cash(T?) = 最新快照日 portfolio_position 的 CASH cash_amount（基线）
                             + SUM(confirmed CASH buys  WHERE confirm_date > 快照日 [AND confirm_date <= T])
                             − SUM(confirmed CASH sells WHERE confirm_date > 快照日 [AND trade_date <= T])
                             − SUM(pending CASH sells [WHERE trade_date <= T])
                             + SUM(confirmed event cash_change WHERE ex_date > 快照日 [AND ex_date <= T])
```

* **时点口径**（#70/#78）：现金流出（sell）的资金承诺锚定**下单日 trade\_date**，不论 pending/confirmed（消除 pending→confirmed 翻转后预留隐身）；流入（buy）仍须 confirmed 且 confirm\_date <= T 才计入。T（as\_of\_date）为空时不设上限。
* 快照生成走 `_generate_portfolio_position` 增量累加路径（前一日 CASH 基准 + 窗口内 confirmed CASH trades + event `cash_change` 增量 + `manual_market_value` 绝对覆盖）；有快照时 `calculate_available_cash` 直接读快照基线，无快照时降级为 `compute_cash_balance`。
* **现金中转约束**：卖出 pending 不自动增加可用现金，买入只能用已有可用现金；不足时须先卖后买两步操作。
* **CASH trade 来源受限**：仅由申赎、基金调仓配对、跨平台现金转移三条路径生成（均预置 `transfer_group`）；`trade.transfer_group` 为 **NOT NULL**，REST 禁止直接创建 `product_code="CASH"` 的交易（`CASH_TRADE_FORBIDDEN`）。
* **平台维度**：现金按平台分别追踪，`portfolio_position` 的 CASH 记录唯一约束为 `(portfolio_code, product_code, market, platform_code, snapshot_date)`；申购/赎回必须指定 `platform_code`（现金归属平台）。跨平台转移的状态机见 §3.3。
* **在途资金虚拟产品**（#93）：`portfolio_position` 除 CASH 行外还有 `IN_TRANSIT_BUY` / `IN_TRANSIT_SELL` 两类现金行，由 `snapshot_service._compute_in_transit_amounts` 每日独立计算、不继承前日。`IN_TRANSIT_BUY`（买入在途）= 已扣款但基金份额未确认（CASH sell 已确认、基金 buy 待确认）；`IN_TRANSIT_SELL`（卖出在途）= 已卖出但到账未确认（基金 sell 已确认、CASH buy 待确认）。两者 `market=""`、`shares=NULL`、`cash_amount` 恒正，种子产品定义见 §4.4。快照表不存分类列（#128 起 `asset_type` 已删列），**现金行一律以 `cash_amount IS NOT NULL` 判定**（CHECK 约束保证与 shares 恰有其一），CASH 与在途行由此自然落入现金口径。

### 2.3 实时可用量计算

冻结份额/现金必须**实时计算**，不能仅读快照 frozen 字段。

```
基金可用份额   = 最新快照份额 − SUM(pending卖出) − SUM(confirmed卖出 WHERE 快照未生成)
投资人可用份额 = 最新快照份额 − SUM(pending赎回) − SUM(confirmed赎回 WHERE 快照未生成)
可用现金       = 见 §2.2 calculate_available_cash
```

### 2.4 净值·成本·市值

* **初始净值固定 1.0000**：首次申购确认时净值 = 1.0000，份额 = 金额（无需行情）。
* **净值稳定性**：申购/赎回/现金分红/份额拆分合并 → 净值不变；调仓 → 净值可能变化。
* **市值** = Σ(场内份额 × 收盘价) + Σ(场外份额 × 净值) + Σ(非净值型资产金额)。非净值型资产金额即 `portfolio_position` 中 `cash_amount IS NOT NULL` 的行（含 CASH 与 IN\_TRANSIT 两类现金行），故 `total_value = Σ(fund market_value) + Σ(CASH cash_amount) + Σ(IN_TRANSIT cash_amount)`；`portfolio_value_snapshot.in_transit_total` 单独记录在途合计。
* **净值** `unit_price = total_value / total_shares`（4 位小数）。
* **快照净值严格匹配**（#96）：取价禁止向前回退——普通基金严格取 `price_date == snapshot_date` 当日净值，QDII 严格取 T-1（前一交易日）净值；任一持仓缺失即抛 `MISSING_NAV` 拒绝生成（`_generate_portfolio_position` 逐产品收集后统一抛出，message 列缺失产品），与 trade 确认侧严格口径一致；`_check_price_data_completeness` 预校验同口径，重算整区间在删除任何快照前拦截。
* **份额统一 2 位小数**（ROUND\_HALF\_UP，第 3 位 ≥5 进位；负数按绝对值对称、远离零进位，符合场外基金行业惯例，误差计入基金财产）：产生点（申购确认 `amount/nav`、调仓买入 `amount/price`、卖出/赎回用户输入、份额事件变动计算）统一经 `app/utils/quantize.py::quantize_shares` 量化；读取/累加路径不量化。净值 4 位不变。
* **金额统一 2 位小数**（#94，ROUND\_HALF\_UP，负数对称语义同份额，量化误差 < 0.005 计入基金财产）：产生点（卖出/赎回确认 `shares×nav`、买入金额与手续费用户输入、申赎金额、现金分红 `cash_change`、forced\_adjustment 用户填写、`manual_market_value` 写入、现金转移金额、trade PUT 直改）统一经 `quantize_amount` 量化；读取/累加路径不量化，现金闸门保持**精确比较**（无容差）。估值口径（`market_value`/`total_value`/`unit_price`）保持 4 位不进现金账本；DB 字段仍为 Numeric(15,4)，字段收紧留作后续迁移。
* **卖出/赎回输入份额先量化再校验**：量化到 2 位后与可用份额**精确比较**（无容差），超出返回 `INSUFFICIENT_SHARES`；买入/转移金额同理先量化再与可用现金精确比较。
* **成本价**：首次 = 组合净值；后续 = `(old×cost + new×price)/(old + new)`。**赎回按申请日净值**计算，不是确认日净值。

### 2.5 交易日约束

所有交易操作（申购、赎回、调仓、现金进出、事件日期）仅允许在交易日进行。判断依据：`trading_calendar` 表 `is_open = true`。非交易日返回 `NON_TRADING_DAY`。

***

## 3. 状态机与生命周期

### 3.1 组合状态（`portfolio.status`）

```
draft ──首次申购确认──▶ active ──close──▶ closed ──reactivate──▶ active
```

* 创建时为 `draft`；首次申购确认后自动置 `active`（`started_at` 记录）。
* 关闭前检查：存在 pending 申赎或 pending trade → `PENDING_TRANSACTIONS_EXIST`；已关闭再关 → `PORTFOLIO_ALREADY_CLOSED`；仅 `closed` 可 `reactivate`（否则 `PORTFOLIO_NOT_CLOSED`）。
* 已关闭组合禁止申赎/调仓，但可查询历史。

### 3.2 交易/申赎/事件状态

三者共用 `pending / confirmed / cancelled`，均支持 confirm / unconfirm / cancel：

* **确认（confirm）**：申赎确认时计算份额/金额并生成配对 CASH trade；trade 确认时按 `product.confirm_days` 计算 `confirm_date`（可传参覆盖，用于补录），并取 T 日净值/收盘价；事件确认时从 `entitlement_date` 快照回写 `entitlement_shares` 并计算变动值。
* **取消确认（unconfirm）**：回退至 pending。**快照保护**——若 `confirm_date`（trade/subscription）或 `ex_date`（event）及之后已有快照，拒绝并返回 `SNAPSHOT_DEPENDENCY`。申赎 unconfirm 会物理删除配对 CASH trade（`transfer_group="sub_{id}"`）。
* **取消（cancel）**：仅 pending 可取消，置 `cancelled`。场内 trade 不可 cancel（`CANNOT_CANCEL_EXCHANGE`）。已 confirmed 的 trade/subscription 不可直接 PUT/DELETE（`CANNOT_MODIFY_CONFIRMED` / `CANNOT_DELETE_CONFIRMED`），须先 unconfirm。

### 3.3 transfer\_group 原子翻转

confirm / unconfirm / cancel 基金腿时，配对 CASH 腿通过 `trade_service.sync_transfer_group` 自动同步状态与金额；delete 基金腿时级联删除配对 CASH 腿。**#93 起各腿保持创建时设定的独立确认日**——`sync_transfer_group` 不再传播 `confirm_date`（仅传播 `trade_date`/`status`/金额）；unconfirm 时 CASH 腿按方向回退默认确认日（买入扣款 T 日即 `trade_date`、卖出到账默认与基金确认日一致）。`attach_paired_cash_leg` 新增 `cash_confirm_date` 参数：缺省按基金腿方向推导（买入扣款 T 日、卖出到账同基金确认日），亦可显式覆盖。

**现金跨平台转移**（`cash_transfers.py`）是 transfer\_group 的特例，复用 `trade` 表，一次转移生成两条 CASH 腿（sell + buy）：

* **当天完成**（`cross_day=False`）：两腿立即 confirmed，`confirm_date = transfer_date`。
* **跨天到账**（`cross_day=True`，#93 非对称模型）：转出方（sell）当日 confirmed、`confirm_date = transfer_date`；转入方（buy）pending、`confirm_date = next_trading_day`，次日经 `confirm` 端点确认。非对称状态保证 D 日 NAV 不因在途转移虚跌（转出方当日扣减，转入方在途不虚增）。`confirm_cash_transfer` 确认组内所有仍为 pending 的 CASH legs（向后兼容旧对称模型）。
* 跨天判断（`list_cash_transfers`）：以 buy 腿为准——`buy.status != "confirmed"` 或 `buy.confirm_date > buy.trade_date`。在途期间转入腿 pending 不计入目标平台可用现金；已确认转出腿正常扣减源平台现金。

### 3.4 快照删除与重算

* **删除快照**（`_delete_existing_snapshots`）自动级联回退：`confirm_date==D` 的申购退回 pending 并删除关联 CASH trade；`ex_date==D` 或 `entitlement_date==D` 的 confirmed 事件退回 pending；基金级父事件的子记录（`parent_event_id`）被物理删除。批量删除从最新日倒序、逐日 commit。
* 遵循**快照连续原则**，不能仅删除中间的快照，删除某日的快照其后的快照也一并删除。
* **重算**（`recalculate_snapshots`）为**单一事务**：删除任何快照前先对整区间做净值完整性预校验，失败直接拒绝、不删任何快照；随后逐交易日「删旧快照 → 级联回退 → 重建 → auto\_confirm」全程不 commit，任一日失败记录 error 并停止，由调用方按 errors 统一 rollback/commit——对外表现为「要么完整成功，要么无变化」。`auto_confirm_after_snapshot` 每日后自动重确认 `apply_date==D` 的申购、`confirm_date==D` 的 trade、`ex_date==D` 的事件，单笔失败仅记录为 `auto_confirm_failed`、不阻断当日流程。

***

## 4. 后端架构

### 4.1 分层目录与职责

| 目录                                                  | 职责                                                                                          |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `app/routers/`                                      | HTTP 薄适配层：解析参数、鉴权（`Depends`）、调 service、`db.commit()`、序列化；业务错误交全局 handler，不写 try/except 业务分支 |
| `app/services/`                                     | 全部业务规则/不变量/计算/状态机/ORM 读写；**只抛领域异常、不 import fastapi、不 commit（可 flush）**                      |
| `app/models/`                                       | SQLAlchemy 表模型                                                                       |
| `app/schemas/`                                      | Pydantic 请求/响应模型                                                                            |
| `app/utils/`                                        | 安全（密码/Token/登录锁）等工具                                                                         |
| `app/config.py` / `database.py` / `dependencies.py` | 配置、DB 会话、鉴权依赖                                                                               |

**分层约定（router 为 service 薄适配器）**：业务逻辑单一实现于 service，REST 共用，杜绝并行实现漂移。

* **事务边界属于 session 拥有者**：service 收到的是调用方注入的 session，不 `commit`/`rollback`（可 `flush`）；REST 在 router `db.commit()`（部分失败语义的端点如 recalculate 按 errors 决定 rollback/commit）。**合理例外**（自己就是 session 拥有者/调用方）：自持 `SessionLocal` 的后台执行体（sync job 线程、scheduler 触发体）与 `task_runner` 编排层的 checkpoint 提交（逐日快照回补、逐产品远程同步，需保留部分成功）可自行 commit。
* **领域异常统一**：service 抛 `app/services/exceptions.py::BusinessError`（携 `code`/`message`/`http_status`/`details`）；`main.py` 全局 handler 映射为 `JSONResponse{"detail": {"error": code, "message": message}}`（保持前端契约；默认 422、重复创建类 400、NOT\_FOUND 404）。service 内**禁止** import/抛 `HTTPException`。

### 4.2 路由与 API 前缀

端点以 `backend/app/main.py` 注册为准；CLI 机读契约见 §6 `ir schema`。

> 前缀约定：所有资源挂 `/api/<资源名>`（如 `/api/snapshots/...`）；`cash_transfers` 作为 `portfolios` 子资源挂 `/api/portfolios/{code}/cash-transfer`；日志/任务/通知/数据源在 `/api/system/*` 二级命名空间。

### 4.3 核心服务

业务核心集中在四个服务模块（函数级细节读源码）：

* **`snapshot_service.py`**：快照生成/重算/校验；三表固定生成顺序（§2.1）；`_generate_portfolio_position` 增量累加（§2.2）；`_compute_in_transit_amounts` 算在途（§2.2）；`_delete_existing_snapshots` 级联回退、`auto_confirm_after_snapshot` 自动重确认（§3.4）。
* **`position_service.py`**：可用现金/份额实时计算（§2.2/§2.3）；`update_cash_position` 现金重估写 `manual_market_value` 绝对替换（绝不直写 `portfolio_position`；同日存在 confirmed CASH trade 时返回 warnings 提示覆盖将压制交易效果）；覆盖层查询/删除后需重算快照回退自然值。
* **`trade_service.py`**：调仓创建/确认/取消；配对 CASH 腿与 transfer\_group 同步（§2.2/§3.3）。
* **`subscription_service.py`**：申赎创建/确认；首次申购净值 1.0000 并激活组合（§2.4/§3.1）。

其余模块中需记住的设计点：`snapshot_recalc_job.py`（#89 异步重算：复用 sync\_job 表 + 线程池，同类型单 active 锁，终态经 `GET /api/sync-jobs/{id}` 轮询）；`product_service.py::calculate_confirm_days` 为确认天数单一实现。其他服务职责读各文件 docstring。

### 4.4 数据模型与关键约束

表结构与全部唯一约束以 `app/models/` 为准。需记住的设计决策：

* `trade.transfer_group` **NOT NULL**（每笔 trade 必属一个业务组），唯一约束 `(transfer_group, product_code, trade_type)`：基金腿与 CASH 腿按 `product_code` 区分、现金转移两腿按 `trade_type` 区分、申赎为单腿 `sub_{id}`，故 NOT NULL 下仍无碰撞。
* `portfolio_position` 有 CHECK 约束：`shares` 与 `cash_amount` 二者恰有其一（净值型 vs 非净值型）。
* `share_change_event` 双日期分级：`ex_date`（除息日，应用日）+ `entitlement_date`（权益登记日，基数日），要求 `ex_date > entitlement_date` 且均为交易日；`parent_event_id` 为基金级拆分子记录自引用。
* 外键删除行为均为 **RESTRICT**，通过业务流程（关闭/停用）管理生命周期，保留历史数据。
* **虚拟产品**（#93）：除 `CASH`（`scripts/init_data.py` 种子）外，迁移 0006 另种子 `IN_TRANSIT_BUY` / `IN_TRANSIT_SELL`，与 CASH 同构（`market=""`、`product_type="IN_TRANSIT"`、`confirm_days=0`）；以 `product_code` 区分方向。维度标签（#128）：CASH 产品 `asset_class_code=ASSET_CASH`、其余四维 NULL；IN_TRANSIT 五维全 NULL。
* **资产分类五维度字典**（#128）：`asset_classification` 是正交维度值字典（`code/dimension/name/sort_order/description`），五个维度 asset_class（股票/债券/商品/现金，维持 4 类，REITs/另类按需再加）/region/style/size/segment（股票行业·债券期限·商品品种共用一维）。产品以 5 个 FK 列挂维度值。字典种子单一事实来源为 `app/constants/asset_dimensions.py`（迁移 0008/0009、init_data.py、conftest 三方共用）；**维度值按需扩展（YAGNI），不为假想需求预留空值**；**asset_class 的 `sort_order` 即前端饼图/分区色板序位，变更即改色**。分类信息只在 positions API 读侧派生（产品五维 join 字典，code+name 成对输出），快照表无分类列；前端二级分组默认股票→region、债券/商品→segment、现金平铺（组合级 display_config 配置归后续 issue）。
* **适用关系双层落库**（#135 矩阵落库）：运行期事实来源为 DB（常量为种子源），`validate_dimension_tags` 四层校验叠加、只收紧不放松——①存在性+dimension 匹配；②`is_active` 软失效（无物理删除；update 仅校验实际变化字段的新值，存量引用停用值不阻断其他编辑）；③维度级规则表 `asset_class_dimension_rule`（required/optional，**无行=forbidden，无规则行的大类=现金型全 forbidden**——新建大类配规则后运行期即可用，无需发版）；④值级关联表 `asset_dimension_applicability`（多对多，产品所选值必须关联其 asset_class）。产品五维标签的「必填/禁止」语义由此两表驱动，不再硬编码。

### 4.5 配置与运行

* 配置项以 `app/config.py` + `.env` 覆盖为准；迁移在 `alembic/`，启动时自动 `upgrade head`。**注意 0006（#93）与 0008（#128）均不可逆**：0006 扩展 8 处 code 列至 String(20)、新增 `in_transit_total`、种子 IN\_TRANSIT 产品（幂等设计）；0008 维度化重构 asset_classification、product 加 4 个维度 FK 列并回填、**DROP `portfolio_position.asset_type`**（回填校验先于任何破坏性操作，失败即中止不留半成品）。
* 调度：`scheduler_enabled`；`init_tasks.py` 确保任务记录存在并同步文案，但不覆盖已有 cron\_expr。
* 数据源：Tushare / AkShare，`data_sources` 路由读写 `.env`；安全：登录失败锁定、Token 过期/黑名单、改密后强制重登（参数明细见 `config.py`）。

***

## 5. 前端架构

技术栈版本以 `frontend/package.json` 为准（Next.js + React + Tailwind + shadcn/ui + Zustand + react-query；E2E 用 Playwright）。

> **前端视觉规范**（语义色/涨跌色/图表色/数字格式/字号，issue #127）见 `docs/design/visual-spec.md`——写 frontend/ 代码前必读（Claude Code 另经 `.claude/rules/visual-spec.md` path-scoped 自动加载）。

### 5.1 双端路由与 Middleware（约定）

* 移动端 `/m/` 前缀、PC 端根路径；`src/middleware.ts` 按 User-Agent 自动重定向；未登录（无 `token` cookie）重定向到对应登录页。页面清单直接看 `frontend/src/app/**/page.tsx`；移动端多为薄壳页，套 `MobileLayout` 后渲染共享内容组件。

### 5.2 组件复用与质量门禁（约定）

* 复用三层：完全共享（`hooks/`、`stores/`、`components/ui/`、`types/`）→ 共享业务组件（`components/shared/`，以 `variant: "desktop" | "mobile"` + `basePath` 适配双端）→ 端侧独立（`components/mobile/`、`desktop/`、`layout/`、`charts/`）。
* API 层 `src/lib/api/` 按域拆分、经 `index.ts` barrel 统一导出（`@/lib/api`）；`next.config.js` 将 `/api/:path*` rewrite 到后端。
* **质量门禁**：构建期强制 ESLint + tsc，0 error 才能通过 `next build`。

***

## 6. CLI 工具

`ir-cli` 是独立轻量 HTTP 客户端（typer + httpx），入口 `ir_cli.main:app`（`ir`），通过 HTTP 调用运行中的后端。命令清单以 `ir --help` / `ir schema` 为准，完整使用手册见 `ir-cli/CLI_MANUAL.md`。

ir-cli 的 `ir schema` 已含响应字段契约（`commands.<group>.<sub>.output.fields`，`*`前缀=默认摘要字段、`?`后缀=可空）与 `--index` 索引模式（极简命令索引，再按 `ir schema <group>` 按需加载）；契约由 `ir-cli/scripts/gen_response_fields.py` 从 `backend/openapi.json` 生成，CI 做一致性校验。

***

## 7. 约束与边界速查

> 规则本体见第 2、3 章；错误码定义见 `app/services/exceptions.py`（机读契约 `ir schema`）。本章只列**读代码不易拼出**的规则语义与易踩坑。

### 7.1 申购赎回

* 申购输入**金额**（份额 = 金额 / 申请日净值）；赎回输入**份额**（金额 = 份额 × 申请日净值）。
* 申请日必须晚于最新快照日（`DATE_BEFORE_SNAPSHOT`）；份额/金额先量化到 2 位再与可用量**精确比较**（§2.4）。
* 申赎必填 `platform_code`（现金归属平台）；非首次申购要求申请日存在组合快照（`NAV_NOT_AVAILABLE`）。

### 7.2 调仓交易

* 金额：买入 `amount = actual_amount − fee`、`shares = amount/price`；卖出 `amount = actual_amount + fee`。
* **可用现金时点口径**：pending 卖出不增加可用现金；买入按扣款平台校验可用现金（§2.2），确认时不足同样拒绝（`skip_cash_check` 仅限 auto\_confirm 路径）。
* **确认取价**：`confirm_date` 创建时即按 `product.confirm_days` 设定（`confirm` 可传参覆盖，补录用）；场内用成交价（录入时必填）、场外严格用 T 日净值（含 QDII；未同步则拒绝，禁止向前查找；可传 `sync_nav`/`--sync-nav` 在 MISSING\_NAV 时自动回填净值并重试一次，#90）；QDII 快照/市值用 T-1 净值。场外确认可选传入价格，仅与 T 日净值做一致性校验（不一致 `PRICE_NAV_MISMATCH`），不覆盖净值。
* 防重：同组合/产品/市场/平台/方向/交易日且金额（买）或份额（卖）相同的 pending/confirmed 交易，未传 `allow_duplicate` 报 `DUPLICATE_TRADE`（cancelled 不算）。
* 仅给 product\_code 且一码多市场（LOF）须显式指定 market（`MARKET_AMBIGUOUS`，`details.available_markets` 列可选项）；场内 trade 不可 cancel。

### 7.3 份额变动事件

* **分级**：基金级（`share_split`/`share_merge`/`bonus_share`，`platform_code` 空，确认时按平台自动拆子记录）；平台级（`cash_dividend`/`reinvest_dividend`/`forced_adjustment`，每个有持仓平台各录 1 条）。
* 日期约束：`ex_date > entitlement_date` 且均为交易日；`ex_date` 须晚于最新快照日。平台级未全覆盖有持仓平台默认阻断（`PLATFORM_NOT_COVERED`），`force_cover=true` 降为 warning。
* 确认时从 `entitlement_date` 快照回写 `entitlement_shares`，按事件类型计算变动值（公式读 `share_change_event_service.py`）。

### 7.4 组合管理

* 关闭/重开/删除投资人的生命周期保护见 §3.1（pending 交易阻断关闭、份额为零才能删投资人等）；持仓表禁止手动 CRUD（`POSITION_TABLE_PROTECTED`），现金修正走 `cash-position` 覆盖层（§7.5）。

### 7.5 易错陷阱（补充）

1. 现金市值修正走 `POST /positions/portfolio/{code}/cash-position` 写 `manual_market_value`（绝对替换），**不直接改 `portfolio_position`**；写入后需重新生成快照。
2. LOF 拆分为两条记录（场内/场外分别处理）。
3. 组合份额仅因申购赎回变化；分红再投资只影响成分基金份额。
4. 投资人不支持强制物理删除——份额需为 0 才能删。
5. 幂等性缓存（`idempotency_cache`）24 小时过期，批量调仓用 `Idempotency-Key`。
6. 分类信息只从 positions API 读侧派生（#128）：快照表无分类列，不要在写侧/快照链路重新引入 asset_type 冗余；判断现金行用 `cash_amount IS NOT NULL`，不用产品类型字符串。产品维度标签改动走 product create/update（service 层矩阵校验），不直改 DB。

***

## 8. 开发流程约定

> 单人 + AI 编程协作的工作流约定。**代码是唯一事实来源**；本约定只约束动作边界，不做过度流程。

### 8.1 分支模型

| 分支     | 角色    | 规则                   |
| ------ | ----- | -------------------- |
| `dev`  | 开发草稿线 | 日常小修直接 push；可随时推翻重来  |
| `main` | 生产交付线 | 合入即触发 CI → CD 自动部署上线 |

* **合 `main` 永远走 PR**（CI 全量门禁：SQLite pytest + MySQL 8.4 方言/迁移链 + ir-cli 契约 + 前端 lint/build）。
* **分支命名**：`feature/<issue号>-<简述>`、`hotfix/<issue号>-<简述>`、`release/<版本>`；AI 代理干活可用 `trae/xxx`、`codex/xxx` 前缀。**合完即删**，不堆积。改动前先 `git fetch` 确认基线：dev 是开发草稿线，**常态领先于 main**；仅 hotfix 场景（先合 main 再合 dev）下 main 会暂时含有 dev 尚未合入的提交。

### 8.2 Issue 约定

* **新功能 / 大改 / 涉及业务规则或 DB 迁移**：必须先提 issue 再动手；修 bug 若影响面大或需留痕，同样先提 issue。
* **修复类 issue 要点**：现象（操作 → 报错 → 期望）→ 根因 → 影响面 → 修复方向 → 验收断言。
* **需求类 issue 要点**：背景/目标 → 现状与问题 → 方案推演（表格对比）→ 选定方案 → 待实现改动（文件级）→ 验收断言。
* **验收断言必须可勾选**（"执行 X → 得到 Y"）：它是给 AI 的验收标准，也是后续测试用例的来源。
* 完整模板见 `.github/ISSUE_TEMPLATE/`（bug\_report / feature\_request）。

### 8.3 PR 约定

* PR 描述必含：改动内容 / 关联 issue（`fixes #N` 自动关闭）/ 测试验证 / 部署影响（DB 迁移、新依赖、回滚要点）。
* 模板见 `.github/PULL_REQUEST_TEMPLATE.md`。
* **合入 `main` 前 CI 必须全绿**；上线后冒烟：health check + `ir portfolio list` + 关键数据抽查。

### 8.4 提交信息

* Conventional Commits 风格：`fix:` / `feat:` / `docs:` / `refactor:` / `chore:`，附简短说明并尽量带 issue 号（如 `fix(snapshot): 快照净值严格匹配 (#96)`）。

### 8.5 AI Angent理铁律

1. **改完必须验证**：本地测试绿 + 能说明改动影响；验证不了的改动不提交。
2. **排查/审查中发现的问题只提 issue，不直接改代码**，由任务所有者决定修复方式。
3. **动手前确认分支**：AI 默认在当前分支提交；被要求改大功能/新功能时，先开 `feature/` 分支。
4. **不得引入未要求的依赖或表结构改动**；涉及 DB 变更必须同步提供 Alembic 迁移脚本。
5. **仓库文档（README/AGENTS/runbook）随代码同一次提交更新**；设计决策与方案记录进 issue 讨论。
6. 当你执行一项任务发现有任何执行细节不明确时，你必须向我提问，而不是自做主张，在我回答之后仍有不明确的行细节时，你需要向我追问，直到了解了所有细节。
7. **AGENTS.md 只写读代码发现不了的内容**（可发现性过滤）：agent 读代码/grep 能拿到的信息（路由、枚举、错误码、表结构、版本号）不写入，只留设计决策、组织约定与易踩坑；新增内容前先自问「这条读源码能拿到吗」。
