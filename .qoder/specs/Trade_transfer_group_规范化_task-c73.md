# Trade transfer_group 规范化（issue #53 跟进）

## Summary
issue #53 三处问题点已在评估中确认存在。本计划在开发阶段（无历史数据兼容负担）下，通过四类改动强制交易现金流水规范：
1. **提取共享助手** `attach_paired_cash_leg`，消除 router 与 CLI 的重复逻辑；
2. **CLI `trade create` 对齐 router**：非 CASH 基金买/卖生成 `transfer_group` + 配对 CASH 腿；
3. **禁止裸 CASH 交易**：REST 与 CLI 均以 `CASH_TRADE_FORBIDDEN` 拒绝直接创建 `product_code="CASH"` 的交易；
4. **DB 层 NOT NULL**：模型 + Alembic 0003 迁移将 `trade.transfer_group` 置为非空，并同步修正测试工厂与相关测试。

核心不变量：CASH 交易只能来自申赎（`sub_{id}`）、基金调仓配对（`rebal_{uuid}`）、跨平台现金转移（裸 uuid）三条已设 `transfer_group` 的路径。

---

## Change 1 — 共享助手（trade_service.py）
文件：`backend/app/services/trade_service.py`

新增 `attach_paired_cash_leg`，把当前散落在 `routers/trades.py` L241–265 的配对 CASH 腿构造逻辑集中：

```python
import uuid
from decimal import Decimal

def attach_paired_cash_leg(db, fund_trade, cash_amount, confirm_date, status="pending"):
    """为基金腿生成 transfer_group 并构造/加入配对 CASH 腿。返回 CASH 腿。"""
    group = f"rebal_{uuid.uuid4().hex[:12]}"
    fund_trade.transfer_group = group
    cash_trade = Trade(
        portfolio_code=fund_trade.portfolio_code,
        platform_code=fund_trade.platform_code,
        product_code="CASH", market="",
        trade_type="sell" if fund_trade.trade_type == "buy" else "buy",
        shares=None, amount=cash_amount, price=Decimal("1"),
        fee=Decimal("0"), actual_amount=cash_amount,
        trade_date=fund_trade.trade_date, confirm_date=confirm_date,
        status=status, transfer_group=group,
    )
    db.add(cash_trade)
    return cash_trade
```

> `cash_amount` 采用 router 现有语义 = 基金腿 `actual_amount`（买入=支出含费，卖出=收入）。放在 service 层可被 router/CLI 共用，且不引入循环依赖（`trade_service` 已 import `Trade`）。

## Change 2 — REST 路由（routers/trades.py）
文件：`backend/app/routers/trades.py`

- **禁止裸 CASH（主）**：在产品校验之后（[L138](file:///home/collyn/projects/InvestRing/backend/app/routers/trades.py#L138) 之后、价格校验之前）新增早退守卫：
  ```python
  if trade.product_code == "CASH":
      raise HTTPException(status_code=422, detail={
          "error": "CASH_TRADE_FORBIDDEN",
          "message": "不支持直接创建 CASH 交易，请使用现金转移或申购赎回入口"})
  ```
- **改用助手**：将 [L241–267](file:///home/collyn/projects/InvestRing/backend/app/routers/trades.py#L241-L267) 的 `if trade.product_code != "CASH":` 块替换为：
  ```python
  db.add(new_trade)
  attach_paired_cash_leg(db, new_trade, actual_amount, expected_confirm_date)
  ```
  删除原 `else: db.add(new_trade)`（裸 CASH）分支——此分支因早退守卫已不可达，一并移除以防回归。保持行为与现有通过的 router 测试一致（纯提取重构）。
- 从 `trade_service` 增补 import：`attach_paired_cash_leg`（`sync_transfer_group` 已导入）。

## Change 3 — 后端 CLI（cli/commands/trades.py）
文件：`backend/cli/commands/trades.py`（`create_trade` [L64–143](file:///home/collyn/projects/InvestRing/backend/cli/commands/trades.py#L64-L143)）

- **禁止裸 CASH**：在产品校验后新增 `if product_code == "CASH": error("CASH_TRADE_FORBIDDEN", "不支持直接创建 CASH 交易，请使用现金转移或申购赎回入口")`。
- **补齐 confirm_date**（对齐 router“日期字段齐备”）：新增 `from app.services.trading_utils import is_trading_day, get_next_trading_day`，计算 `expected_confirm_date = get_next_trading_day(db, td, days=product.confirm_days or 0)`，在 buy/sell 分支构造 `new_trade` 时传入 `confirm_date=expected_confirm_date`。
- **生成配对 CASH 腿**：在 buy（L114–120）与 sell（L130–136）构造 `new_trade` 后、`db.flush()` 前：
  ```python
  from app.services.trade_service import attach_paired_cash_leg
  db.add(new_trade)
  attach_paired_cash_leg(db, new_trade, actual_amount_d, expected_confirm_date)
  db.flush(); db.refresh(new_trade)
  ```
  两腿在 `cli_context()` 单次 commit 中原子落库（`success()` 触发 `SystemExit` → 提交）。CASH 腿金额沿用 `actual_amount_d`（buy=实际支出；sell=`actual_amount or 0`），与 router 完全一致。

## Change 4 — 模型 + 迁移
文件：`backend/app/models/trade.py`
- [L20](file:///home/collyn/projects/InvestRing/backend/app/models/trade.py#L20) 改为 `transfer_group = Column(String(36), nullable=False)`；更新 L14–19 注释：删去“普通单腿 trade 该字段为 NULL”，改述为“每笔 trade 均隶属一个业务组”。保留 `uq_trade_transfer_group`（NOT NULL 下仍无碰撞——见风险分析）。

新文件：`backend/alembic/versions/0003_trade_transfer_group_not_null.py`
- `revision='0003'`，`down_revision='0002'`。
- `upgrade()`（幂等，遵循 0001/0002 的 try/except 约定，避免 `main.py` L25 启动期 upgrade 抛错崩溃）：
  ```python
  def upgrade():
      try:
          op.execute("UPDATE trade SET transfer_group = CONCAT('legacy_', id) WHERE transfer_group IS NULL")
      except Exception:
          pass
      try:
          op.alter_column('trade', 'transfer_group', existing_type=sa.String(36), nullable=False)
      except Exception:
          pass
  ```
- `downgrade()`：`alter_column(... nullable=True)`，同样 try/except 包裹。
- 迁移权威目标为生产 MySQL；全新库经 `main.py` L8 `create_all` 已由模型直接建为 NOT NULL，迁移对其为无操作。SQLite 现存开发库若 `alter_column` 报错由 try/except 吞掉（开发期可接受，不影响启动）。

## Change 5 — 测试工厂 + 受影响测试
文件：`backend/tests/factories.py`（`create_trade` [L229–272](file:///home/collyn/projects/InvestRing/backend/tests/factories.py#L229-L272)）
- 顶部 `import uuid`；构造 `Trade` 时：`transfer_group=transfer_group or f"test_{uuid.uuid4().hex[:12]}"`。保留形参默认 `None`，仅在构造时兜底，使全部约 30 处工厂调用无需逐一修改即满足 NOT NULL 且各自唯一（避免 `uq_trade_transfer_group` 碰撞）。更新 L250 docstring。
- 该改动纯为满足 NOT NULL：工厂只建单行、不生成第二条 CASH 腿，`compute_cash_balance`/快照行为不变。

文件：`backend/tests/integration/test_trades.py`
- 修正手工 `Trade(...)` 直插（约 L592）：补 `transfer_group=f"rebal_test_{uuid.uuid4().hex[:8]}"`。
- 新增用例：REST `POST /api/trades` 传 `product_code="CASH"` → 422 `CASH_TRADE_FORBIDDEN`。

文件：CLI 测试（若无 CLI trade 测试文件则新增；否则在既有文件补充）
- 断言 CLI 基金 buy/sell 后产生共享同一 `rebal_` `transfer_group` 的两行（基金腿 + CASH 腿）；
- 断言 CLI `--product-code CASH` 被 `CASH_TRADE_FORBIDDEN` 拒绝。

## Test Plan
1. `cd backend && ../.venv/bin/python -m pytest tests/integration/test_trades.py -q`（覆盖 router 配对、金额同步、新 CASH 拒绝、直插修正）。
2. `../.venv/bin/python -m pytest tests/unit/test_position_service.py tests/unit/test_snapshot_service.py tests/integration/test_positions.py -q`（验证工厂兜底不破坏现金/快照计算）。
3. `../.venv/bin/python -m pytest tests/e2e -q`（业务流）。
4. 全量 `../.venv/bin/python -m pytest -q` 确认 0 失败。
5. 手动/脚本冒烟：CLI `ir trade create --type buy ...` 返回后校验 DB 出现基金腿 + CASH 腿且 `transfer_group` 一致、非空。
6. 迁移验证：对 MySQL 执行 `alembic upgrade head` 与 `downgrade -1` 往返无误。

## Dependencies（执行顺序）
- Change 1（助手）→ 前置于 Change 2、3。
- Change 5（工厂兜底）必须与 Change 4（模型 NOT NULL）**同批或先落地**，否则 SQLite `create_all` 建表后全部工厂插入违反 NOT NULL。
- Change 4 模型改动应在 Change 2、3 完成后（否则 CLI 旧逻辑造出的单腿 trade 违反 NOT NULL）。
- Change 2、3 共用错误码 `CASH_TRADE_FORBIDDEN`，保持 API/CLI 一致。
- 迁移 `down_revision='0002'` 必须正确串接，且在 `main.py` 启动期 upgrade 下安全（try/except）。

## Risks & Mitigations
- **启动期迁移崩溃**：`main.py` L25 无 try/except；迁移自身以 try/except 包裹 + 预置 backfill，确保不抛。
- **唯一约束碰撞**：`(transfer_group, product_code, trade_type)` 在 NOT NULL 下仍安全——rebal 对按 `product_code`（基金 vs CASH）区分；现金转移对按 `trade_type`（sell/buy）区分；申赎为单腿 `sub_{id}`；独立操作用新 uuid。工厂兜底每次调用独立 uuid，多条 CASH 种子不冲突。
- **CLI 原子性**：两腿须在 `success()`（触发提交）前 `db.add`，单次 `db.flush()`；`IntegrityError` 由 `cli_context` 回滚并报 `ALREADY_EXISTS`，两腿同回滚。
- **禁止裸 CASH 影响既有调用**：已核实所有合法 CASH 创建走 subscription/cash_transfers/rebal 配对，均不经 `create_trade` else 分支；测试 POST body 均为 ETF/基金产品。实施时再 grep `POST /api/trades` body 复核无 `product_code="CASH"`。
- **可用现金一致性**：基金 buy 生成 pending CASH sell → `calculate_available_cash` 已预留 pending CASH sell，正确减少可用现金；买入前置校验（router L161 / CLI L107）在 CASH 腿生成前执行，无重复计减。
- **SQLite 现存开发库**：`alter_column` 在 SQLite 会失败但被 try/except 吞掉；全新库经 `create_all` 已 NOT NULL，故仅影响极少数陈旧本地库，可删库重建。

## Rejected Alternatives
- **保持 nullable + 仅应用层校验**：不满足“DB 层保证”的诉求，无法防旁路写入，拒绝。
- **迁移使用 `batch_alter_table` 追求 SQLite 完全可移植**：SQLite 批处理需重建表并复现复合外键 `(product_code, market)` 与唯一约束，复杂且回归风险高；迁移权威目标是 MySQL，SQLite 由 `create_all` 覆盖，故采用 try/except 包裹的直接 `alter_column`，`batch_alter_table` 仅作备选。
- **逐一修改约 30 处工厂调用点传入 transfer_group**：改动面大、易漏，改为工厂内单点兜底（最小回归面）。
- **仅替换 else 分支而不加早退守卫**：早退守卫更清晰且能避免对 CASH 输入跑完 buy/sell 校验；两者并施（守卫为主 + 移除死分支）。
- **CLI 内联复制 router 配对逻辑（不提取助手）**：造成三处重复（router/CLI），长期维护差；改为共享 `attach_paired_cash_leg`，并以既有 router 测试守护重构安全。
- **错误码 `CASH_TRADE_NOT_ALLOWED`（方案 B 命名）**：统一采用 `CASH_TRADE_FORBIDDEN`，与语义及现有风格一致。
