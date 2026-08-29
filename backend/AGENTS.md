# backend/AGENTS.md — 后端模块操作指南

> 业务不变量/领域模型/分层约定见根 `AGENTS.md`（§2-§4），本文件只写**怎么跑、易踩坑**。

## 跑测试

```bash
cd backend && pytest tests -q
```

- **本地默认跑影响面子集**：全量耗时长，全量回归由 CI 兜底（合入前 `CI OK` 强制）。按改动文件圈定，如 `pytest tests/test_snapshot_service.py -q -x` 或 `pytest tests -q -k snapshot`；影响面拿不准就宁宽勿窄。上面整条命令留给怀疑大改动或合入前自检。
- **测试库优先级**（`tests/conftest.py::_load_test_db_url`）：env `TEST_DB_URL` > `backend/.env.test`（gitignored，按需配置本地/远程 MySQL）> 降级 `sqlite:///./test_investring.db`。CI 的 SQLite job 不设 `TEST_DB_URL`（也不存在 .env.test），MySQL job 显式设置。
- **会话开始 `drop_all + create_all`**（干净起跑）；会话结束**不清理**——跑完可直接登录本地前端浏览种子数据。
- fixture 层级：session（`test_engine`、`_seed_base_data`）→ autouse（认证全局状态隔离）→ function（`test_db`/`client`/`admin_headers`/`sample_portfolio` 等），业务数据一律用 function 级 fixture/factories 造，不动 session 种子。
- pytest 配置在 `pyproject.toml`（`--strict-markers`），新增 marker 须登记。

## 种子数据（单一事实来源）

`tests/seed_base.py::seed_base_data(db)`：维度字典、适用关系、4 平台、7 产品、2025-2026 工作日日历、draft 组合 `E2E_PORT`、ADMIN/admin@2026、VIEWER/viewer123。三处消费：pytest（conftest）、CI E2E（`scripts/seed_e2e.py`）、本地 E2E（`scripts/run_e2e_backend.py`）。改种子只改这一处。**前端 E2E 业务冒烟依赖 `E2E_PORT` 存在（无组合时 spec 静默 skip），勿删。**

## 本地启动

```bash
cd backend && uvicorn app.main:app --reload   # 配置见 .env.example
```

启动时序：import 期 `create_all` → lifespan 内 `alembic upgrade head`。**alembic 不能单独从零建库**（迁移依赖 create_all 先建表，如 0007 直接 UPDATE product）。

## 迁移（alembic）

- 新迁移必须提供可逆 downgrade；CI（backend-test-mysql）对最新一条迁移做 downgrade/upgrade 往返验证；确不可逆时 PR 设 `SKIP_DOWNGRADE` 豁免、合入后移除。
- 现有不可逆迁移：**0006、0008**（含 DROP 列），回滚只能靠备份。
- 种子类 DML 写迁移时双方言（SQLite/MySQL）都要过——迁移文件头注释写清幂等设计。

## 依赖

- `requirements.txt` 是镜像与 CI 的**唯一安装来源**（`Dockerfile:30-32` + `ci.yml` 四个 job 均裸 `pip install -r requirements.txt`）；`pyproject.toml` 的 `dependencies` 全是 `>=` 下界，**不参与构建**，改它不改变任何安装结果。加依赖须更新 requirements.txt。
- **传递依赖不显式钉版就等于没钉**：未出现在 requirements.txt 的包，版本由构建时解析决定、仓库零记录。已钉：`click`（uvicorn 传递）、`starlette`（fastapi 传递，#314）。干净环境实测解析 79 个包、requirements.txt 仅声明 30 个，**其余 50 个传递依赖仍浮动**（清单见 issue #314；含 `anyio`、`typing_extensions`、`pydantic_core`、`cryptography`、`greenlet`、`h11`/`httptools`/`websockets` 等可能跨大版本者）。
- **本地 ≠ CI**：pip 不升级已满足下界的已装包 → 同一份 requirements.txt 在本地可能是旧版、干净环境解析成新版；排查版本相关现象先 `pip show <pkg>` 对齐。
- `pip-audit`（`security-scan.yml`）按**声明**解析，抓不到未声明的传递依赖，别当锁文件用。

## E2E 相关脚本

- `scripts/run_e2e_backend.py`：本地 E2E 后端（SQLite 临时库，每次启动重建 + 自动种子，空 lifespan 跳迁移）。
- `scripts/seed_e2e.py`：CI E2E 种子入口，**未设 `DATABASE_URL` 直接拒绝**（防误连）。

## 分层红线（摘要，详见根 §4.1）

service 只抛 `BusinessError` 不 import fastapi、不 commit（可 flush）；router 负责 `db.commit()`；事务例外仅限自持 session 的后台执行体。
