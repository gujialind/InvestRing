# CLI 与后端 API 分层对齐重构

## Summary
当前 `confirm` 类逻辑部分抽到了 service，但 `create/校验/状态机/查询计算` 仍散落在各 router，`backend/cli` 因此重写并已多处漂移。本次按"router/CLI 均为 service 薄适配器"的统一分层，把剩余业务逻辑下沉到 service，修复全部不一致，并消除两处 service 坏味道（`trade_service` 抛 `HTTPException`、`snapshot_service` 反向 import router）。

## 分层约定（本次北极星）
- Service 层：拥有全部业务规则/不变量/计算/状态机/ORM 读写；**只抛领域异常，不 import fastapi**；**不 commit/rollback**（可 flush），事务边界交调用方。
- Router 层：解析参数、鉴权（`Depends`）、调 service、序列化；业务错误由全局异常处理器统一映射，不再写 try/except 业务分支；`db.commit()` 在 router。
- CLI 层：`backend/cli` 调同一 service，`cli_context` 负责 commit 与异常→JSON 错误码。
- `ir-cli`：保持 HTTP 透传，仅补齐缺失参数/命令。

## Phase 0 — 基础设施：统一领域异常
- 新增 `backend/app/services/exceptions.py`：`class BusinessError(Exception)` 携带 `code:str`、`message:str`、`http_status:int=422`、`details:dict|None`。
- `backend/app/main.py` 注册全局 handler：`BusinessError` → `JSONResponse(status_code=e.http_status, content={"detail": {"error": e.code, "message": e.message}})`，**保持现有前端契约 `detail.error/message` 不变**。
- `backend/cli/context.py`：在 `ValueError` 分支前增加 `except BusinessError as e: error(e.code, e.message)`。
- 迁移现有异常：`subscription_service` 的 `NavNotAvailableError/InvalidStatusError` 改为 `BusinessError` 子类（码 `NAV_NOT_AVAILABLE`/`INVALID_STATUS`）；`trade_service.confirm_single_trade` 内 `HTTPException(MISSING_NAV/PRICE_NAV_MISMATCH)` 改抛 `BusinessError`，并移除 `from fastapi import HTTPException`。

## Phase 1 — 业务逻辑下沉到 service（核心）
补全既有 service：
- `trade_service.py`：新增 `create_trade(...)`（含 `NON_TRADING_DAY`/`PORTFOLIO_NOT_ACTIVE`/`DATE_BEFORE_SNAPSHOT`/`CASH_TRADE_FORBIDDEN`/`MISSING_OR_INVALID_PRICE`、买卖金额/份额计算、`calculate_available_cash/shares` 传 `platform_code`+`as_of_date`、`attach_paired_cash_leg`）、`cancel_trade`（`CANNOT_CANCEL_EXCHANGE`+`sync_transfer_group`）、`unconfirm_trade`（`SNAPSHOT_DEPENDENCY`+重算 confirm_date+`sync_transfer_group`）。
- `subscription_service.py`：新增 `create_subscription(...)`（含 `DATE_BEFORE_SNAPSHOT`、创建即设 `confirm_date`、`calculate_investor_available_shares` 传 `as_of_date`）。
- `position_service.py`：新增 `update_cash_position(...)`——写 `manual_market_value`（绝对替换）并返回 `requires_snapshot_regen`，**杜绝直接写 `portfolio_position`**。

新增 service 模块（逻辑从 router 迁出，router 与 CLI 共用）：
- `share_change_event_service.py`：迁入 `_compute_event_fields`/`_check_platform_coverage`/`_confirm_fund_level_event`，并提供 `create/confirm/cancel/unconfirm` 全套（含 `INVALID_EX_DATE`/`INVALID_ENTITLEMENT_DATE`/`INVALID_DATE_ORDER`/`DATE_BEFORE_SNAPSHOT`/平台分级校验/`MISSING_POSITION_SNAPSHOT`/`CANNOT_UNCONFIRM_CHILD` 与子记录级联）。同步把 `snapshot_service.auto_confirm_after_snapshot` 的 `from app.routers.share_change_events import ...` 改为 import 本 service（**修复反向依赖**）。
- `cash_transfer_service.py`：`create`（对称状态：`cross_day=True` 两腿均 pending、`confirm_date=next_trading_day`；含 `DATE_BEFORE_SNAPSHOT`/`SAME_PLATFORM`/`INSUFFICIENT_CASH`）、`confirm`（两腿同时确认+`TRANSFER_NOT_READY`）、`list` 分组。
- `portfolio_service.py`：`create/close/reactivate/returns/cash_flow/nav_history`（统一 `closed_at` 时间口径，消除 CLI `date.today()` 与 router `datetime.utcnow()` 分歧）。
- `product_service.py`：`calculate_confirm_days`（单一实现，消除 else 分支 0/1 漂移）+ `create/update`。
- `investor_service.py`：`create/update/delete`（`INVESTOR_HAS_SHARES`；统一 `role` 处理策略）。

## Phase 2 — Router 瘦身
各 router 端点改为：校验入参→调 service→`db.commit()`→序列化返回；删除已迁出的 `_calculate_confirm_days`、`_confirm_fund_level_event`、`_compute_event_fields`、`_check_platform_coverage`、现金转移/现金重估内联逻辑；业务异常交全局 handler。`snapshots.py` 的 `bulk delete` 循环迁入 `snapshot_service.bulk_delete_snapshots`。

## Phase 3 — backend/cli 改为委托 service（修复全部不一致）
逐命令改为调用 Phase 1 的 service 并删除重复实现：
- `trades.py`：`confirm`→`confirm_single_trade`；`cancel`/`unconfirm`→对应 service；`create`→`create_trade`；**删除 `_get_nav_for_confirmation`**（向前查找违规）。
- `share_events.py`：`create/confirm/cancel`→service，**新增 `unconfirm`**。
- `cash_transfers.py`：`create/confirm`→service（对称模型）。
- `positions.py`：`update-cash`→`update_cash_position`（写 manual_market_value）。
- `subscriptions.py`：`create`→`create_subscription`（confirm/unconfirm 已在用 service）。
- `portfolios.py`/`products.py`/`investors.py`：改调各自 service。

## Phase 4 — ir-cli 补齐
- `share_events.py`：`create` 增加 `--force-cover` 透传 query；新增 `unconfirm` 命令。
- 核对 `trades create` 的 `--market` 与后端 schema 必填性一致。

## Phase 5 — 测试与文档
- 运行 `cd backend && python -m pytest`；为受影响 service 增/改单测，新增 backend/cli 与 REST 的 parity 测试（同输入→同错误码/同副作用，尤其配对 CASH 腿、事件拆分、对称转移、manual_market_value）。
- 更新 `AGENTS.md`（§4 明确分层约定与新 service 清单）与 `backend/CLI_MANUAL.md`（新增 share-event unconfirm 等）。

## 不一致 → 修复 追踪
| 项 | 位置 | 修复 |
|---|---|---|
| 1/2 | cli trades confirm、`_get_nav_for_confirmation` | 委托 `confirm_single_trade`；删向前查找 |
| 3/4 | cli trades cancel/unconfirm | service 内 `sync_transfer_group`+快照保护 |
| 5 | cli trades create | `create_trade`（快照/价格/平台/as_of_date 校验） |
| 6/7 | cli share-events confirm/create/unconfirm | 事件 service（计算/拆分/校验/新增 unconfirm） |
| 8 | cli positions update-cash | 写 manual_market_value，不碰 portfolio_position |
| 9 | cli cash-transfer create/confirm | 对称状态 service |
| 10 | cli subscriptions create | `create_subscription`（DATE_BEFORE_SNAPSHOT 等） |
| 附 | products confirm_days、portfolio closed_at、investor role | 单一 service 实现，统一口径 |
| 附 | trade_service 抛 HTTPException、snapshot_service import router | 迁 BusinessError、改 import service |

## Assumptions
- 保留 `backend/cli`（方案 B），价值定位为离线/无 server 的管理入口，重构后为 service 薄封装。
- 全局 BusinessError→HTTP 采用 FastAPI 异常处理器，响应体维持 `detail.{error,message}` 以不破坏前端。
- Service 一律不 commit；事务由 router/`cli_context` 收口。
- `auth` 因强 HTTP 语义（Request/Token/黑名单）本次不强制抽 service，仅保持现状；如需可后置。