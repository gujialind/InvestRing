# 业务约束与边界速查

> 规则本体见根 `AGENTS.md` §2-§3；错误码定义见 `app/services/exceptions.py`（机读契约 `ir schema`）。本文件只列**读代码不易拼出**的规则语义与易踩坑。

## 申购赎回

* 创建时申请日必须**晚于最新快照日**（`DATE_BEFORE_SNAPSHOT`）——与确认期要求「申请日已有快照」（`NAV_NOT_AVAILABLE`）是同一时间线两端，见根 §3.3。

* **乱序补录闸门**：确认日早于组合首笔到账日 `started_at` 拒绝 `CONFIRM_BEFORE_STARTED`（相等放行，同日多平台生命线），防回溯污染首窗定价；乱序单走 auto\_confirm 会记 `auto_confirm_failed`，需手动按序处理。

## 调仓交易

* 金额：买入 `amount = actual_amount − fee`、`shares = amount/price`；卖出 `amount = actual_amount + fee`。**卖出金额为纯派生量**（#190）：有价格时 `amount = quantize(shares × price)`、`actual_amount = amount − fee`；创建时显式传入的 amount/actual\_amount（两参同义、`actual_amount` 优先）仅作一致性校验（差值超 0.01 报 `AMOUNT_MISMATCH`），落库恒用推导值——金额即 shares/price/fee 的「校验和」，用于对账；无价格（场外未传价）时创建期占位，确认按 T 日净值重算。

* **PUT 直改与创建同口径**（#182）：编辑 pending 交易时 buy 的 amount/actual\_amount 视为含费现金支出（`actual_amount` 优先），service 层联动重算净额列并镜像 CASH 腿；sell 有价格时与创建同口径（#190）：按新 shares/price/fee 重推导、显式金额仅作对账（场内超差拒绝、场外静默），无价格占位单仍输入为准；改金额/份额/日期实时校验可用量（加回自身 pending 旧值）、非交易日直接拒绝不静默滚交易日、自然键防重排除自身（无 `allow_duplicate`）；CASH 腿仅 notes 放行；校验全部通过前零写入。

* **可用现金时点口径**：pending 卖出不增加可用现金（不足时须先卖后买两步操作，不能预支）；买入按扣款平台校验可用现金（根 §2.6），确认时不足同样拒绝（卖出确认对称校验份额；`skip_available_check` 仅限 auto\_confirm 路径）。

* **确认取价**：`confirm_date` 创建时即按 `product.confirm_days` 设定（`confirm` 可传参覆盖，补录用）；场内用成交价（录入时必填）、场外严格用 T 日净值（含 QDII；未同步则拒绝，禁止向前查找；可传 `sync_nav`/`--sync-nav` 在 MISSING\_NAV 时自动回填净值并重试一次，#90）。场外确认可选传入价格，仅与 T 日净值做一致性校验（不一致 `PRICE_NAV_MISMATCH`），不覆盖净值。快照估值侧与此正交：按产品 `nav_lag_days` 取价（`0`=当日、`N`=前第 N 个交易日；场外 QDII / 互认基金置 1），详见根 §2.3。

* **状态转换拦截码**：场内 trade 不可 cancel（`CANNOT_CANCEL_EXCHANGE`）；已 confirmed 的 trade/申赎不可直接 PUT/DELETE（`CANNOT_MODIFY_CONFIRMED` / `CANNOT_DELETE_CONFIRMED`），须先 unconfirm。

* **跨平台现金转移的跨天判定**（`list_cash_transfers`）以 **buy 腿**为准：`buy.status != "confirmed"` 或 `buy.confirm_date > buy.trade_date` 即计为跨天。在途期间转入腿 pending 不计入目标平台可用现金，已确认转出腿正常扣减源平台现金。

* 防重：同组合/产品/市场/平台/方向/交易日且金额（买）或份额（卖）相同的 pending/confirmed 交易，未传 `allow_duplicate` 报 `DUPLICATE_TRADE`（cancelled 不算）。

* 仅给 product\_code 且一码多市场（LOF）须显式指定 market（`MARKET_AMBIGUOUS`，`details.available_markets` 列可选项）。

## 份额变动事件

* 日期约束：`ex_date > entitlement_date` 且均为交易日；`ex_date` 须晚于最新快照日。平台级未全覆盖有持仓平台默认阻断（`PLATFORM_NOT_COVERED`），`force_cover=true` 降为 warning。

* 输入校验（#279，创建/更新/确认三路径同口径）：`forced_adjustment` 必须至少一项（`shares_change`/`cash_change`）非空，否则 `EMPTY_ADJUSTMENT`；现金型产品（`product_type` 为 CASH/IN_TRANSIT）不接受份额变动（结构型事件无条件拒、其余类型显式 `shares_change` 拒，`SHARES_CHANGE_ON_CASH_PRODUCT`）。

* **market 补全口径**（#258，与调仓 #83 同口径）：创建时 `market` 省略/空串按产品唯一市场自动补全；一码多市场（LOF）报 `MARKET_AMBIGUOUS`；产品不存在报 `PRODUCT_NOT_FOUND`——杜绝 `(product_code, market)` 复合外键违约 500。

* 持仓存在性防线（#278）：`forced_adjustment` 确认时精查权益登记日 `(产品, market, 平台)` 持仓行，无行拒绝 `POSITION_NOT_FOUND`（LOF market 误填提前快失败）；快照生成对份额事件硬拒绝 `POSITION_NOT_FOUND`：①指向不存在的持仓行（不静默新建 0 份额行）、②作用于现金行（`cash_amount IS NOT NULL` 的行存在但不得承载份额变动），负向调整打空持仓行产出 `event_zeroed_position` 告警（不阻断）。

## 量化产生点（份额 / 金额统一 2 位，口径见根 §2.7）

* `quantize_shares` 产生点：申购确认 `amount/nav`、调仓买入 `amount/price`、卖出/赎回的用户输入份额、份额事件的变动计算。

* `quantize_amount` 产生点（#94）：卖出/赎回确认 `shares×nav`、买入金额与手续费用户输入、申赎金额、现金分红 `cash_change`、`forced_adjustment` 用户填写、`manual_market_value` 写入、现金转移金额、trade PUT 直改。

* 读取/累加路径**不量化**；现金与份额闸门保持精确比较（无容差）。

## 组合管理

* 关闭前检查：存在 pending 申赎或 pending trade → `PENDING_TRANSACTIONS_EXIST`；已关闭再关 → `PORTFOLIO_ALREADY_CLOSED`；仅 `closed` 可 reactivate（否则 `PORTFOLIO_NOT_CLOSED`）。生命周期语义见根 §3.2。

* 持仓表禁止手动 CRUD（`POSITION_TABLE_PROTECTED`），现金修正走 `cash-position` 覆盖层（见下）；投资人份额为零才能删。

## 易错陷阱

1. 现金市值修正走 `POST /positions/portfolio/{code}/cash-position` 写 `manual_market_value`（绝对替换），**不直接改 `portfolio_position`**；写入后需重新生成快照。该覆盖层**可删除**，删后同样需重算快照才会回退到自然计算值。
2. LOF 拆分为两条记录（场内/场外分别处理）。
3. 组合份额仅因申购赎回变化；分红再投资只影响成分基金份额。
4. 投资人不支持强制物理删除——份额需为 0 才能删。
5. 幂等性缓存（`idempotency_cache`）24 小时过期，批量调仓用 `Idempotency-Key`。
6. 分类信息只从 positions API 读侧派生（#128）：快照表无分类列，不要在写侧/快照链路重新引入 asset\_type 冗余；判断现金行用 `cash_amount IS NOT NULL`，不用产品类型字符串。产品维度标签改动走 product create/update（service 层矩阵校验），不直改 DB。
7. 传递依赖不写进 `backend/requirements.txt` 就等于没钉（#314，fastapi 的 starlette 曾长期浮动）；且 fastapi ≥0.141 改了 `app.routes` 结构，会让遍历路由的鉴权门禁（#256）静默空通过（#306）——升 fastapi/starlette 必须连带复核这道门禁是否还在真扫描。
