# InvestRing 开发指南 (AGENTS.md)

> 为 AI 编程助手提供项目级快速参考。本文只记录**读代码发现不了**的内容：设计决策、业务不变量、组织约定与易踩坑；路由、枚举、错误码、表结构、版本号等以源码为准。

***

## 1. 项目概览

**InvestRing** 是我设计的供自己使用的投资组合管理工具，本质是一个支持净值化、多投资人的记账系统，为个人和家庭财富管理、大类资产配置提供完整的数据体系。适用的持仓资产目前限于公募基金（场内 ETF、场外基金、LOF 两栖）与现金，**不支持个股**（产品类型枚举见 §2.3）。所有资产人民币计价，无汇率换算。

**Monorepo 布局**（技术栈版本明细以 `frontend/package.json` / `backend/pyproject.toml` 为准）：

| 目录                                        | 内容                                                           |
| ----------------------------------------- | ------------------------------------------------------------ |
| `backend/`                                | FastAPI + SQLAlchemy 后端；含 `app/`（应用）、`alembic/`（迁移）、`tests/` |
| `frontend/`                               | Next.js 前端（App Router，双端路由，技术栈见 `frontend/AGENTS.md`）                |
| `ir-cli/`                                 | 独立轻量 HTTP 客户端 CLI（typer + httpx）                             |
| `nginx/`、`scripts/`、`docker-compose*.yml` | 部署与运维                                                        |

**运行入口**：后端 `backend/app/main.py`（启动初始化行为读源码）；前端 `npm run dev`；`ir` CLI 的说明见 `ir-cli/AGENTS.md`。

**模块指南分层**（issue #224）：各模块的架构约定与操作级细节（怎么跑测试/E2E、种子来源、契约流程、易踩坑）在 `backend/AGENTS.md`、`frontend/AGENTS.md`、`ir-cli/AGENTS.md`；业务约束速查见 `docs/design/business-constraints.md`（改后端业务代码时经 Rule 自动提醒）。本文件只保留全局业务不变量与组织约定，不重复。

***

## 2. 领域模型

> 本章讲**静态语义**（有什么、是什么、怎么算），§3 讲**状态如何流动**。两章合起来是业务规则的单一事实来源；写路径的逐字段校验与错误码语义见 `docs/design/business-constraints.md`。

### 2.1 实体全景与双层账本

InvestRing 是**净值化记账系统**：投资人按净值申购/赎回组合份额，组合内部再把钱配置到具体产品。**两层账本各记各的，由每日组合净值唯一连接**：

```
投资人层账本   investor_holding（份额 / 成本价 / 市值）
   ▲   只由申购·赎回驱动 —— 组合总份额仅因申赎变化
   │
   ├── 枢纽   portfolio_value_snapshot：unit_price = total_value / total_shares
   │
   ▼   由调仓·份额事件·手动重估驱动 —— 只改资产构成与总市值，不改组合份额
资产层账本   portfolio_position（净值型持仓 + 现金 + 在途）
```

由此可直接判定任何变更的落点：只动资产层的（调仓 / 事件 / 重估）不改组合份额、可能改净值；动两层的（申赎）改份额、不改净值。**净值只在快照生成时被定义**——没有当日快照就没有当日净值，一切依赖净值的操作都要先有快照。

| 实体                    | 在模型中的角色（细节见括注小节）                  |
| --------------------- | --------------------------------- |
| `portfolio`           | 净值化记账单元；初始净值 1.0000、份额 0    |
| `investor`            | 组合份额持有人；申赎是资金进出组合的**唯一**通道         |
| `product`             | 组合内部资产，三类：净值型 / 现金 / 在途（§2.3）      |
| `platform`            | 托管归属；现金与基金持仓分平台记，**投资人份额不分平台**     |
| `subscription`        | 投资人 ↔ 组合的份额增减（§3.3）               |
| `trade`               | 组合内部资产调整；基金腿必配等额 CASH 腿（§3.4）     |
| `share_change_event`  | 产品份额/现金的外生变动；双日期生效（§3.5）          |
| `manual_market_value` | 现金绝对重估覆盖层，优先级最高（§2.5）             |
| `trading_calendar`    | 唯一日期权威，`is_open = true` 才是交易日     |
| 快照三表                  | 每日结果账本，只增不改（§2.4）                 |

**交易日是所有日期字段的硬约束**：申赎、调仓、现金进出、事件日期只允许落在交易日，否则 `NON_TRADING_DAY`；「下一个交易日」「前第 N 个交易日」一律查 `trading_calendar`，不做自然日推算。

### 2.2 组合与投资人

* **首次申购确认按 1.0000 计价**（份额 = 金额，无需行情）——组合创建即净值 1.0000、份额 0。

* **份额同质**：所有投资人持有同一种组合份额，同日同净值，无平台维度、无份额分级；投资人之间的差异只有份额数与成本价。

* **成本价**（两层账本同构口径）：加权平均 `(old_shares × old_cost + new_shares × new_price) / (old_shares + new_shares)`——投资人层按申购净值加权、资产层按买入价加权；**减少方（赎回/卖出）只减份额、不动成本价**。

* **净值稳定性**：申购/赎回/现金分红/份额拆分合并 → 净值不变；调仓 → 净值可能变化（价差与手续费）。

### 2.3 产品与取价

* `product_type` 三类：**净值型** `ETF` / `OEF` / `LOF`（估值 = 份额 × 单价，场内取收盘价、场外取净值，价格落 `price_record`）；**现金** `CASH`（直接记 `cash_amount`，重估走 `manual_market_value`）；**在途** `IN_TRANSIT`（`IN_TRANSIT_BUY` / `IN_TRANSIT_SELL` 两只虚拟产品，§2.5）。

* `market` 枚举 `CN_EXCHANGE`（场内）/ `CN_OTC`（场外）/ `HK_MUTUAL`（香港互认）；`(code, market)` 是产品复合主键，故 LOF 一码两市场是**两条独立产品记录**，只给 `product_code` 时须显式指定 market。

* **快照取价严格匹配**（#96/#178/#228）：取价日**只由产品 `nav_lag_days` 决定**——`0` 取 `price_date == snapshot_date`，`N` 取交易日历上前第 N 个交易日（场外 QDII 与香港互认基金为 `1`，净值晚一日披露；其余为 `0`）。**禁止向前回退**，任一持仓缺价即 `MISSING_NAV` 拒绝生成快照。

* 快照取价与 **trade 确认取价正交**：确认恒取 T 日价，确认间隔由落库的 `confirm_days` 决定；`is_qdii` 是纯展示标签（仅创建时用于推导 `confirm_days` 默认值），不参与取价分支。

* 五维资产分类（asset\_class / region / style / size / segment）只在**读侧派生**，快照表无分类列（#128）；维度字典与校验矩阵见 `backend/AGENTS.md` §1.4。

### 2.4 快照三表

**三张表只增不改**：`portfolio_position`（资产层）、`portfolio_value_snapshot`（净值枢纽）、`investor_holding`（投资人层）。

* 每交易日汇总生成一次（**不是每笔交易生成**），永不 UPDATE，保留完整历史（ORM `before_update`/`before_delete` 事件兜底禁止实例级改删）。

* **固定生成顺序**：`portfolio_position` → `portfolio_value_snapshot` → `investor_holding`——资产层市值决定净值，净值再回填投资人层市值/收益（顺序即 §2.1 的数据流方向）。

* **生成前提**：影响该日的申赎/交易/事件必须都已确认，不存在 `confirm_date <= snapshot_date`（事件为 `ex_date <= target_date`）的 pending 记录，否则校验返回 failed。

* **快照连续原则**：快照逐日增量依赖前一日，必须严格按交易日顺序连续生成（从最新快照日的下一个交易日起），失败即停、不允许跳过。单日生成入口只接受「最新快照日」（重建最新一日）或「其下一个交易日」，否则 `SNAPSHOT_NOT_CONTINUOUS`。删除侧同样不许留空洞（§3.6）。

### 2.5 现金账本

所有现金变动**显式记录**，不从申赎/调仓隐式反推。三类影响源：

| 来源             | 记录表                             | 生效日与关联                                             |
| -------------- | ------------------------------- | -------------------------------------------------- |
| 交易（申赎/调仓/转移）   | `trade`（CASH buy/sell）          | `confirm_date`；同组记录共享 `transfer_group`             |
| 事件（现金分红等）      | `share_change_event.cash_change` | `ex_date`                                          |
| 手动重估           | `manual_market_value`           | `value_date` 绝对替换；优先级高于当日交易/事件，并作为后续快照的增量基线        |

* **CASH trade 来源受限**：只能由申赎确认、基金调仓配对、跨平台现金转移三条路径生成（均预置 `transfer_group`）；REST 直接创建 `product_code="CASH"` 的交易一律 `CASH_TRADE_FORBIDDEN`。

* **平台维度**：现金按平台分别追踪（`portfolio_position` 的 CASH 行唯一键含 `platform_code`），申赎必须指定平台；基金买/卖可经 `cash_platform_code` 让 CASH 腿落在另一平台（#91），免去前置的平台间现金转移。

* **在途资金**（#93）：`IN_TRANSIT_BUY`（已扣款、基金份额未确认）与 `IN_TRANSIT_SELL`（基金已卖出、现金未到账）两类现金行，**每日独立计算、不继承前日**，`cash_amount` 恒正——它们是配对两腿确认日之差（§3.4）的账面表现，保证在途期间总市值不塌陷。

* **现金行判定一律用 `cash_amount IS NOT NULL`**（CHECK 约束保证与 `shares` 恰有其一），CASH 与在途行由此自然落入现金口径——不要用产品类型字符串判断。

### 2.6 可用量实时计算（写闸门）

冻结份额/现金必须**实时计算**，不能只读快照的 frozen 字段。

```
可用现金(T?) = 最新快照日 portfolio_position 的 CASH cash_amount（基线）
             + Σ confirmed CASH buy   (confirm_date > 快照日 [AND confirm_date <= T])
             − Σ confirmed CASH sell  (confirm_date > 快照日 [AND trade_date   <= T])
             − Σ pending   CASH sell  ([trade_date <= T])
             + Σ confirmed event cash_change (ex_date > 快照日 [AND ex_date <= T])
```

* **时点口径**（#70/#78）：现金**流出**锚定下单日 `trade_date`、不论 pending/confirmed（消除 pending→confirmed 翻转瞬间的预留隐身）；**流入**须 confirmed 且 `confirm_date <= T`。`T`（as\_of\_date）为空时不设上限。

* 无任何快照时降级为全量历史口径 `compute_cash_balance(T)` = Σ(confirmed CASH trades, `confirm_date <= T`) + Σ(confirmed events, `ex_date <= T`)。

* **基金可用份额** = 最新快照份额 − Σ(pending 卖出) − Σ(快照未覆盖的 confirmed 卖出) + Σ(快照未覆盖的 confirmed 事件**负向** `shares_change`)（#277）。事件增量只计平台级行（基金级父记录持汇总值，防父子双计）；**正向变动不计入**——保守低估，防事件被撤销后已放行的卖出成事实超卖。

* **投资人可用份额** = 最新快照份额 − Σ(pending 赎回) − Σ(快照未覆盖的 confirmed 赎回)。份额变动事件**不并入**（只作用于资产层，§3.5、#277）。

### 2.7 计价与精度

* **总市值** `total_value` = Σ(净值型 `market_value`) + Σ(现金行 `cash_amount`)。净值型 = 场内份额 × 收盘价 + 场外份额 × 净值；现金行含 CASH 与在途两类，在途合计另记在 `portfolio_value_snapshot.in_transit_total`。

* **精度分层**：份额与金额统一 **2 位小数**（`quantize_shares` / `quantize_amount`，ROUND\_HALF\_UP，负数按绝对值对称、远离零进位，符合场外基金行业惯例，量化误差计入基金财产）；净值与估值口径（`unit_price` / `market_value` / `total_value`）保持 **4 位**，不进现金账本。量化只在**产生点**做（用户输入、份额/金额换算结果），读取与累加路径不量化——产生点清单见 `docs/design/business-constraints.md`。

* **闸门精确比较**：卖出/赎回份额、买入/转移金额先量化到 2 位，再与可用量**精确比较**（无容差），超出返回 `INSUFFICIENT_SHARES` / `INSUFFICIENT_CASH`。

***

## 3. 业务流程与状态机

### 3.1 通用状态机（trade / subscription / event 三者共用）

```
pending ──confirm──▶ confirmed ──unconfirm──▶ pending
   │
   └──cancel──▶ cancelled（终态）
```

* **确认（confirm）**：各类型的取价/取数口径各自不同，见 §3.3（申赎）/ §3.4（调仓）/ §3.5（事件）。

* **取消确认（unconfirm）**：回退至 pending。**快照保护**——`confirm_date`（trade/申赎）或 `ex_date`（事件）当日及之后已有快照则拒绝 `SNAPSHOT_DEPENDENCY`（要改先删快照）。申赎 unconfirm 会物理删除配对的 CASH trade。

* **取消（cancel）**：仅 pending 可取消，`cancelled` 是终态；场内 trade 不可 cancel。已 confirmed 的记录不可直接 PUT/DELETE，须先 unconfirm。

* **负现金防护**（#203）：unconfirm 自身不设现金守卫（守卫会阻断快照删除的级联回退），改在两处消费点拦截——赎回确认生成配对 CASH sell 腿时校验平台可用现金（`INSUFFICIENT_CASH`）、快照生成对 CASH `cash_amount < 0` 硬阻断（`NEGATIVE_CASH`）。

### 3.2 组合生命周期（`portfolio.status`）

```
draft ──首次申购确认──▶ active ──close──▶ closed ──reactivate──▶ active
          ▲                        │
          └─unconfirm 至零确认申购─┘
```

* 创建时为 `draft`，首次申购确认后自动置 `active`；`closed` 组合禁止申赎/调仓但可查询历史；仅 `closed` 可 reactivate。关闭前存在 pending 申赎或 pending trade 则阻断。

* **`started_at` = 现存 confirmed 申购的最小 `confirm_date`**（#180，到账事实，与激活轮次正交）：确认时为空则写入、unconfirm 时取最小值重算、close/reactivate 不触碰。重算后若无 confirmed 申购且 `status == active` 则回退 `draft`（`closed` 不回退——那是用户意图态）。

### 3.3 申购与赎回（投资人 ↔ 组合）

**定价时间线**：下单日 `apply_date` = T（需晚于最新快照日，此刻 T 日净值尚未定）→ T 日收盘生成快照、净值定档 → T+1（下一个交易日，创建时即写入 `confirm_date`）确认，按 **T 日净值**计价。两道日期闸门（创建期要求 T 晚于最新快照日、确认期要求 T 已有快照）是同一条时间线的两端，不矛盾。

* 申购输入**金额**（份额 = 金额 / T 日净值），赎回输入**份额**（金额 = 份额 × T 日净值）。确认时申请日无快照即 `NAV_NOT_AVAILABLE`——禁止回退旧净值或用当前净值。

* 唯一例外是**首窗**（#179）：申请日无快照且不存在 `confirm_date <= apply_date` 的 confirmed 申购时（等价于申请日零持仓、净值结构性恒 1.0）按 1.0000 计价，覆盖首日多平台/分笔申购。

* 必填 `platform_code`：确认后按该平台增减现金（申购生成 CASH buy、赎回生成 CASH sell，`transfer_group = sub_{id}`）。**平台只是现金落点，确认后不与投资人保持关联**。

### 3.4 调仓与现金转移（组合内部）

两类操作都复用 `trade` 表、以 `transfer_group` 成组，组内多腿状态原子一致。

**① 基金买卖**（`rebal_{uuid}`）：基金腿 + 等额 CASH 腿——买入 = 基金 buy + CASH sell，卖出 = 基金 sell + CASH buy。

* **原子翻转**：confirm / unconfirm / cancel 基金腿时，`trade_service.sync_transfer_group` 自动同步 CASH 腿的 `trade_date` / `status` / 金额；delete 基金腿级联删除 CASH 腿。

* **各腿保持独立确认日**（#93）：`confirm_date` 不传播——买入扣款为 T 日（即 `trade_date`）、卖出到账默认与基金确认日一致，创建时可显式覆盖。两腿确认日之差就是在途窗口，账面表现为 `IN_TRANSIT_*` 行（§2.5）。

**② 跨平台现金转移**（裸 `{uuid}`）：一次转移 = CASH sell（转出平台）+ CASH buy（转入平台）。当天完成（`cross_day=False`）两腿立即 confirmed；**跨天到账**（`cross_day=True`，#93 非对称模型）转出腿当日 confirmed、转入腿 pending 且 `confirm_date = next_trading_day`，次日经 confirm 端点确认——非对称保证 D 日净值不因在途转移虚跌（转出方当日扣减、转入方在途不虚增）。

### 3.5 份额变动事件（产品份额/现金的外生变动）

* **只作用于资产层**：改成分产品的份额与现金，**不改组合总份额**（组合份额只因申赎变化，§2.1）。

* **双日期**：`entitlement_date`（权益登记日，取基数份额）→ `ex_date`（除息日，变动生效），要求 `ex_date > entitlement_date`。确认时从 `entitlement_date` 快照回写 `entitlement_shares`，再据此算变动值。

| 级别  | 事件类型                                                 | 落库形态                                                  |
| --- | ---------------------------------------------------- | ----------------------------------------------------- |
| 基金级 | `share_split` / `share_merge` / `bonus_share`        | `platform_code` 空，确认时按有持仓平台自动拆子记录（`parent_event_id`）  |
| 平台级 | `cash_dividend` / `reinvest_dividend` / `forced_adjustment` | 每个有持仓的平台各录 1 条                                        |

### 3.6 快照生成 · 删除 · 重算

* **生成**：按 §2.4 连续原则逐交易日推进；每日生成后 `auto_confirm_after_snapshot` 自动重确认 `apply_date == D` 的申购、`confirm_date == D` 的 trade、`ex_date == D` 的事件，单笔失败只记 `auto_confirm_failed`、不阻断当日流程。

* **删除即级联回退**：删某日快照会把依赖该日净值的确认记录退回 pending——`apply_date == D` 的 confirmed 申赎（连带删除配对 CASH trade）、`ex_date == D` 或 `entitlement_date == D` 的 confirmed 事件（基金级父事件的子记录物理删除）。**级联任一笔回退失败即整体中止、不删除任何快照**（#203）。按连续原则，删某日必须连带删除其后所有快照，不能只挖中间一天。

* **重算**（`recalculate_snapshots`）是**单一事务**：删除任何快照前先对整区间做净值完整性预校验，失败直接拒绝、不删任何快照；随后逐交易日「删旧快照 → 级联回退 → 重建 → auto\_confirm」全程不 commit，任一日失败即记录 error 并停止，由调用方按 errors 统一 rollback/commit——对外表现为**要么完整成功，要么无变化**。

* **零快照 + 目标日前已有确认交易**（#180）：单日 `generate` 拒绝 `SNAPSHOT_REQUIRES_RECALCULATE`——无前序快照时增量窗口退化为仅目标日、早期到账被静默漏掉（首快照「失忆」），须用 `recalculate` 从最早 `confirm_date` 逐日重建。目标日恰为最早到账日的真正首次生成不受影响。

***

## 4. 开发流程约定

> 单人 + AI 编程协作的工作流约定。**代码是唯一事实来源**；本约定只约束动作边界，不做过度流程。

### 4.1 分支模型（GitHub Flow，单长期分支，issue #211）

| 分支     | 角色            | 规则                                                                              |
| ------ | ------------- | ------------------------------------------------------------------------------- |
| `main` | 唯一长期分支（生产交付线） | 受 ruleset 保护：禁删除/禁强推 + require PR + required check `CI OK`；合入即触发 CI → CD 自动部署上线 |

* **一切改动经 `feature/` → PR → `main`**：从最新 `origin/main` 不从本地旧 ref 重建。拉短命分支（`feature/<issue号>-<简述>`、`hotfix/<issue号>-<简述>`；AI 代理可用 `trae/xxx`、`codex/xxx` 前缀），

* 手动部署（`deploy.yml` `workflow_dispatch`）只接受已有镜像 tag（回滚/重部署）。

### 4.2 Issue 约定

* **新功能 / 大改 / 涉及业务规则或 DB 迁移**：必须先提 issue 再动手；修 bug 若影响面大或需留痕，同样先提 issue。

* 按模板提交 `.github/ISSUE_TEMPLATE/`（bug\_report / feature\_request / chore）。

* **标题前缀与 Conventional Commits 对齐**：`[bug]` / `[feat]` / `[chore]`（含文档/运维类）。


### 4.3 PR 约定

* 使用 PR 模板 `.github/PULL_REQUEST_TEMPLATE.md`。

### 4.4 commit 信息

* Conventional Commits 风格：`fix:` / `feat:` / `docs:` / `refactor:` / `chore:`，附简短说明并尽量带 issue 号（如 `fix(snapshot): 快照净值严格匹配 (#96)`）。

### 4.5 AI AGENT铁律

1. **改完必须验证**：本地跑**改动影响面**的测试且绿即可，不要求全量（全量回归由 CI 的 `CI OK` 在合入前兜底；影响面圈定宁宽勿窄，如动 `snapshot_service` 应连带快照/申赎/调仓相关测试；影响面圈定程序见 `backend/AGENTS.md`「跑测试」节）+ 能说明改动影响；验证不了的改动不提交。
2. **排查/审查中发现的问题只提 issue，不直接改代码**，由任务所有者决定修复方式。
3. **不得引入未要求的依赖或表结构改动**；涉及 DB 变更必须同步提供 Alembic 迁移脚本。
4. **仓库文档（README/AGENTS/runbook）随代码同一次提交更新**；设计决策与方案记录进 issue 讨论。
5. 当你执行一项任务发现有任何执行细节不明确时，你必须向我提问，而不是自做主张，在我回答之后仍有不明确的行细节时，你需要向我追问，直到了解了所有细节。
