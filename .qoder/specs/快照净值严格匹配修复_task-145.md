# Issue #96：快照生成净值严格匹配，缺失即拒绝

## 背景与根因

`backend/app/services/snapshot_service.py` 两处 `price_date <= X` 降序取 first 造成静默回退：

1. `_generate_portfolio_position`（约 1003-1021 行）：生成持仓快照时取净值回退到最近历史值，且 `price_record` 为 None 时仅留 `unit_price=None`，不报错不警告 —— issue 复现的直接原因。
2. `_check_price_data_completeness`（约 1603-1612 行）：预校验闸门普通基金分支同样用 `<= target_date`，导致 07-30 有净值即可通过 07-31 的校验（QDII 分支已是严格 `== prev_date`）。该闸门被 `generate_daily_snapshots`（176-181 行）与 `recalculate_snapshots` 整区间预校验（314-333 行）消费。

调用链均已确认可安全接收异常：REST router（BusinessError→全局 handler 映射 `detail.{error,message}`；ValueError→422 VALIDATION_FAILED）、`cli_context`（BusinessError→原始错误码 exit 1）、`recalculate` 逐日循环（except→errors→break→调用方整体 rollback）、`catch_up`/`run_nav_sync`（逐日 try/except，失败日回滚并停止）。调度任务 `run_nav_sync` 先同步净值再生成快照，fail-fast 正是期望行为。

## 核心修改：`backend/app/services/snapshot_service.py`

### 1. `_generate_portfolio_position`（生成侧硬性保证，约 1001-1021 行）

```python
elif product:
    # #96 严格净值匹配：普通基金=target_date 当日，QDII=T-1 交易日，禁止向前回退
    if product.is_qdii:
        nav_date = _prev_trading_day(db, target_date, 1)
        nav_rule = "T-1(QDII)"
    else:
        nav_date = target_date
        nav_rule = "T"
    price_record = db.query(PriceRecord).filter(
        PriceRecord.product_code == product_code,
        PriceRecord.market == market,
        PriceRecord.price_date == nav_date,
    ).first()
    if price_record:
        unit_price = Decimal(str(price_record.unit_price))
        market_value = pos_data["shares"] * unit_price
    else:
        missing_nav.append(f"{product_code}({market}) [{nav_rule}={nav_date}]")
```

- `missing_nav` 在持仓循环前初始化；循环结束后、`warnings` 计算前统一抛出：
  `raise BusinessError(code="MISSING_NAV", message=f"快照生成失败，以下持仓缺少所需净值: {'; '.join(missing_nav)}", details={"portfolio_code": ..., "target_date": str(target_date), "missing": missing_nav})`
- 逐产品收集后一次抛出，message 列出全部缺失产品与所需日期（满足验收 1）。
- 零持仓行在价格查询前已被 `continue` 跳过、CASH/IN_TRANSIT 行不进 `elif product` 分支，均不受影响。
- 抛出点在 `db.add_all(positions)` 之前，REST/CLI/recalculate 路径均整体回滚，不产生半截快照（满足验收 5：目标日无快照行、最新快照日不变）。

### 2. `_check_price_data_completeness`（闸门对齐，约 1603-1612 行）

- 普通基金分支改为 `PriceRecord.price_date == target_date`（去掉 order_by），缺失项消息改为 `f"{product_code}({market}) [T={target_date}]"`（指出产品与日期，验收 1）。
- 更新 docstring 为严格语义（普通基金=当日、QDII=T-1），与生成侧一致。
- 效果：重算整区间预校验在删除任何快照前拦住 NAV 缺失（符合 issue #58「预校验失败不删任何快照」语义，issue 要求的 recalculate 兼容）。

### 3. `generate_daily_snapshots` 闸门错误码（176-181 行）

- 失败项全部为 `check_type == "price_data"` 时改抛 `BusinessError(code="MISSING_NAV", message=f"依赖数据校验失败: ...")`（与 trade 确认侧错误码一致；ir-cli `hints.py` 已有 MISSING_NAV 提示「ir market sync-history 回填后重试」，正好适用）。
- 混合失败（如 pending 交易 + 缺净值）保持现有 `ValueError`→VALIDATION_FAILED 不变。
- `recalculate_snapshots` 预校验路径（自行聚合抛 ValueError）不改，`test_precheck_failure_keeps_snapshots` 等现有测试不回归。

## 测试：新建 `backend/tests/integration/test_snapshot_nav_strict.py`

基建复用 `tests.factories`（`create_product` 支持 `is_qdii`、`create_price_record` 已存在）与 `test_snapshots.py` 的 `_setup_cash_snapshot`+`create_position_snapshot` 模式；conftest 日历工作日均为交易日（D0=2025-06-06 周五，NEXT=2025-06-09 周一，T-2=2025-06-05 周四）。每个用例：D0 日三表快照（含基金持仓 100 份）→ 对 NEXT 日操作。

1. **缺当日净值拒绝**：普通基金仅 D0 有净值 → POST `/api/v1/snapshots/generate` NEXT → 422、`detail.error == "MISSING_NAV"`、message 含产品代码与 `2025-06-09`；`PortfolioValueSnapshot` 无 NEXT 日行、最新快照日仍为 D0（验收 1、5）。
2. **补净值后成功且取当日**：补 NEXT 日净值（值与 D0 不同）→ 200；NEXT 日 `PortfolioPosition.unit_price` == NEXT 日净值（验收 2、4）。
3. **QDII T-1 缺失拒绝且不回退 T-2**：QDII 基金仅 T-2(06-05) 有净值 → 422 MISSING_NAV（验收 3 前半）。
4. **QDII 严格取 T-1**：T-1(06-06)=2.0 与 NEXT(06-09)=3.0 均有净值 → 200 且 `unit_price == 2.0`（验收 3 后半）。
5. **重算预校验严格**：普通基金仅 D0 有净值 → POST `/api/v1/snapshots/recalculate`（D0..NEXT）→ 422 VALIDATION_FAILED 且快照未删（此前 `<=` 会放行，专测闸门收紧）。

## 文档更新

- `AGENTS.md` §2.4 增加一条：快照净值严格匹配（普通基金=快照日当日、QDII=T-1 交易日，`price_date` 精确匹配禁止回退；缺失抛 `MISSING_NAV` 拒绝生成，与 trade 确认侧严格模式一致）。
- `backend/CLI_MANUAL.md` 错误码表：`MISSING_NAV` 描述由「确认时缺少净值数据」扩展为「交易确认/快照生成时缺少净值数据」。

## 验证步骤

1. `cd backend && python -m pytest tests/integration/test_snapshot_nav_strict.py -v`（新用例全绿）
2. `python -m pytest tests/integration/test_snapshots.py tests/integration/test_snapshot_catchup.py tests/integration/test_snapshot_negative_cash.py tests/integration/test_snapshot_recalc_async.py -v`（快照相关无回归）
3. `python -m pytest tests/ -x -q`（全量后端测试）
4. 可选手动复现 issue 场景：`ir snapshot generate --portfolio-code PORT001 --target-date <缺净值日>` 应失败并列出缺失产品与日期。

## 收尾（需用户确认后执行）

- 提交：`fix(snapshot): 快照生成净值严格匹配，缺失当日/T-1净值即拒绝 (#96)`
- `gh issue comment 96` 说明根因与修复点，`gh issue close 96`。

## 假设与边界

- 场内产品（股票/ETF）走非 QDII 分支 → 严格要求 target_date 收盘价，与 `_check_price_data_completeness` 现有结构一致。
- `market_data_service` 的 `get_latest_price`（`<=` 回退）属行情查询/展示用途，不在本 issue 范围，不改。
- 前端无需改动：`useSnapshot` 的 `onError` 通过 `getErrorMessage` 通用展示 `detail.message`，新错误信息直接以 toast 呈现。
