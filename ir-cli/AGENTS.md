# ir-cli/AGENTS.md — CLI 模块指南

> `ir` 是独立轻量 HTTP 客户端（typer + httpx），入口 `ir_cli.main:app`，经 HTTP 调用运行中的后端；完整使用手册见 `CLI_MANUAL.md`，命令清单以 `ir --help` / `ir schema` 为准。

## 1. 跑测试

```bash
pip install -e ir-cli pytest && pytest ir-cli/tests -q   # 仓库根目录执行
```

## 2. 响应字段契约（CI 强制）

后端 API 响应结构变化后必须重新生成契约并**同一次提交**：

```bash
python ir-cli/scripts/gen_response_fields.py    # backend/openapi.json → ir_cli/response_fields.py
python ir-cli/scripts/gen_response_fields.py --check   # CI 用：不一致 exit 1
```

CI 的 `cli-contract-check` job 还校验 `backend/openapi.json` 本身无漂移（`backend/check_openapi.py`）。纯 stdlib 脚本、任意 cwd 可跑。

## 3. 契约语义

`ir schema` 输出含响应字段契约（`commands.<group>.<sub>.output.fields`，`*` 前缀=默认摘要字段、`?` 后缀=可空）与 `--index` 极简索引模式；改命令输出字段时同步更新 `utils.py` 的 SUMMARY_FIELDS 再重新生成。

## 4. 版本

`pyproject.toml` 的 version（`ir --version` 经 `importlib.metadata` 读取）由发布流程从仓库根 `VERSION` 同步，勿手改（见 `docs/reference/versioning.md`）。
