# Issue #132 实施计划：移除 backend/cli（管理 CLI）

## 1. 删除 backend/cli/ 目录与关联测试

- `git rm -r backend/cli/`（23 个 .py 文件，2588 行）
- `git rm backend/tests/integration/test_cli_service_parity.py`（293 行）
- `git rm backend/tests/integration/test_cli_trades.py`（116 行）

## 2. backend/pyproject.toml — 清理打包入口与依赖

文件：`backend/pyproject.toml`

- 删除 `[project.scripts]` 段的 `ir = "cli.main:app"`（第 35-36 行）
- `dependencies` 数组中移除 `"typer>=0.9.0"`（第 29 行）和 `"tqdm>=4.60.0"`（第 31 行），保留 `"click>=8.0.0"`（uvicorn 间接依赖）
- `[tool.setuptools.packages.find]` 的 `include` 从 `["cli*", "app*"]` 改为 `["app*"]`（第 48 行）

## 3. backend/requirements.txt — 同步移除依赖

文件：`backend/requirements.txt`

- 删除第 37-40 行的 CLI 小节中 `typer>=0.9.0` 和 `tqdm==4.67.3`，保留 `click==8.3.3`
- 注释行 `# CLI` 可改为 `# uvicorn dependency` 或直接删除（click 单独留下需注释说明其来源）

## 4. backend/app/database.py — 移除 CLI_MODE 死代码

文件：`backend/app/database.py`

删除以下 3 处：
- 第 8 行注释：`# CLI 模式下禁用 echo，避免 SQL 日志干扰 JSON 输出`
- 第 9 行变量：`_is_cli = os.environ.get("CLI_MODE") == "1"`
- 第 15 行 `echo` 参数从 `echo=settings.debug and not _is_cli` 改为 `echo=settings.debug`

清理后 `import os` 若无其他引用则可保留（`get_settings` 可能间接需要），需确认。

## 5. AGENTS.md — 更新文档引用（6 处修改）

文件：`AGENTS.md`

### 5.1 §1 布局表（第 15 行）
`backend/` 行描述从 `含 app/（应用）、cli/（管理 CLI）、alembic/（迁移）、tests/` 改为 `含 app/（应用）、alembic/（迁移）、tests/`

### 5.2 §1 运行入口（第 20 行）
`两套 ir CLI 的区别见 §6` 改为 `ir CLI 的说明见 §6`

### 5.3 §4.1 分层约定（第 158 行）
`router / CLI 均为 service 薄适配器` 改为 `router 为 service 薄适配器`；`REST 与两个 CLI 共用` 改为 `REST 共用`

### 5.4 §4.1 事务边界（第 160 行）
删除 `，backend/cli 由 cli_context() 统一 commit` 这一句

### 5.5 §4.1 领域异常统一（第 161 行）
删除 `；cli_context 捕获后转 {"error": {"code", "message"}}` 这一句（CLI 异常转换路径已不存在）

### 5.6 §6 CLI 工具（第 217-232 行）整节改写
删除双 CLI 对比表，改写为 ir-cli 单一说明：

```markdown
## 6. CLI 工具

项目提供 `ir-cli`（HTTP 客户端 CLI），通过 HTTP 调用运行中的后端：

| 项 | 说明 |
| ---- | ---- |
| 定位 | HTTP 客户端，调用运行中的后端 |
| 依赖 | typer + httpx（轻量独立包） |
| 入口 | `ir_cli.main:app`（`ir`） |

命令清单以 `ir --help` / `ir schema` 为准。

> 详见 `ir-cli/` 目录文档。

ir-cli 的 `ir schema` 已含响应字段契约（`commands.<group>.<sub>.output.fields`，`*`前缀=默认摘要字段、`?`后缀=可空）与 `--index` 索引模式（极简命令索引，再按 `ir schema <group>` 按需加载）；契约由 `ir-cli/scripts/gen_response_fields.py` 从 `backend/openapi.json` 生成，CI 做一致性校验。
```

### 5.7 §7.4 / §7.5 中的泛指 CLI 引用
- 第 75 行 `REST 与 CLI 均禁止直接创建` → `REST 均禁止直接创建`（ir-cli 经 HTTP 受同一路由约束，无需特别提及）
- 第 57 行 `CLI --cash-platform-code` → 保留（ir-cli 仍有此参数）

## 6. backend/CLI_MANUAL.md — git rm

- `git rm backend/CLI_MANUAL.md`（1255 行，迁移改写由 #131 负责）

## 7. 重新安装 backend 包以刷新 entry_points

- 在 backend 虚拟环境中执行 `pip install -e backend/` 刷新 `investring.egg-info/entry_points.txt`，确认不再含 `cli.main:app`

## 8. 验收

- [ ] `grep -rn "from cli\|import cli\b\|CLI_MODE\|cli_context" backend --include=*.py` 无命中
- [ ] `pytest backend/tests/` 全量通过（SQLite 模式）
- [ ] `ir-cli/scripts/gen_response_fields.py --check` 契约校验通过
- [ ] `pip install -e backend/` 成功，`ir --help` 指向 ir-cli
- [ ] AGENTS.md 全文无「管理 CLI / backend/cli / cli_context / CLI_MODE」表述
- [ ] 容器构建正常（entrypoint alembic + uvicorn 路径无变化）

## 9. 提交与 PR

- 分支：`feature/132-remove-backend-cli`，base 设为 `dev`
- 提交信息含 issue #132 引用
- PR 描述关联 #132 和 #131（文档迁移衔接）
