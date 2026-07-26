# 实时现金计算基线对齐快照口径

## Summary

`calculate_available_cash` 声称"快照基线 + 窗口"，但基线实际通过 `get_cash_value(D)` 全量重算流水 + manual 精确日期匹配。当 manual_market_value 存在于历史日期时，快照已继承覆盖值，实时计算却丢失。需将基线改为直接读 `portfolio_position` 快照表。

## GitHub Issue

创建新 Issue，标题：`[bug] calculate_available_cash 基线与快照生成口径不一致（manual 覆盖继承丢失）`

内容要点：
- 关联 #51（#51 完成了快照侧增量回归，本 issue 对齐实时计算侧）
- 复现场景：manual_market_value(date=D-2) 设置覆盖 -> 生成 D-2、D-1 快照 -> 实时计算读 D-1 快照日基线时用 compute_cash_balance 全量重算，丢失 D-2 的覆盖
- 影响范围：所有调用 calculate_available_cash 的端点（available-cash API、trades 买入校验、cash_transfers 校验、CLI）
- 修复方向：基线直接读 portfolio_position 快照表 CASH amount

## 代码修改

### 1. `backend/app/services/position_service.py` - calculate_available_cash

将 L129-133 基线逻辑替换为：

```python
# 基线：直接读快照表 CASH 持仓（与 _generate_portfolio_position 增量范式口径一致，
# manual_market_value 覆盖已 baked in 快照，自然继承）
if latest_date is not None:
    cash_query = db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_code == portfolio_code,
        PortfolioPosition.product_code == "CASH",
        PortfolioPosition.snapshot_date == latest_date,
    )
    if platform_code:
        cash_query = cash_query.filter(PortfolioPosition.platform_code == platform_code)
    cash = sum(
        Decimal(str(p.amount or 0)) for p in cash_query.all()
    )
else:
    cash = compute_cash_balance(db, portfolio_code, platform_code, as_of_date)
```

- 有快照时：O(1) 查询，口径与快照完全一致
- 无快照时：降级为 `compute_cash_balance`（全量流水），行为不变

### 2. `get_cash_value` 处理

保留函数但更新 docstring，标注其用途缩减为：
- 无快照降级路径的辅助（可选）
- cash-position 端点审计字段展示

不再被 `calculate_available_cash` 调用。

### 3. `backend/tests/unit/test_position_service.py` - 测试更新

- `_seed_cash_baseline` 需追加 `create_position_snapshot` 创建 CASH 持仓快照记录（当前只造了 value_snapshot + trade，未造 position 记录）
- `TestCalculateAvailableCashWithOverride` 中 manual 覆盖测试改为：在 position snapshot 中直接体现覆盖后的 amount（模拟快照生成已 bake in manual），而非依赖 `get_cash_value` 的 manual 精确匹配
- 新增测试用例：`test_manual_override_inherited_from_snapshot`
  - 场景：position snapshot amount=10000（含历史 manual 覆盖），无 manual 记录在 latest_date
  - 断言：calculate_available_cash 返回 10000 + 窗口增量（而非回退到流水值）

### 4. docstring / 注释同步

- `calculate_available_cash` docstring 更新基线描述
- `compute_cash_balance` docstring L35-37 更新（不再作为 calculate_available_cash 有快照时的基线）
- AGENTS.md 中 `calculate_available_cash` 公式描述同步（如有）

## 不变部分

- 窗口增量逻辑（after_trades / pending_sells / after_events）不变
- `compute_cash_balance` 函数本身不变（仍用于审计和无快照降级）
- 快照生成 `_generate_portfolio_position` 不变（已是增量范式）
- `update_cash_position` 端点不变（仍写 manual_market_value）

## 验证

- 运行 `pytest backend/tests/unit/test_position_service.py -v`
- 运行 `pytest backend/tests/ -k "cash" -v` 确认无回归
