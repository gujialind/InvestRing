# 版本号规范与发布流程（issue #375）

> 项目版本**单一事实来源 = 仓库根 `VERSION` 文件**。本文定义 InvestRing monorepo 的 Semver 规范与发布操作；方案推演与设计决策见 issue #375。

***

## 1. 版本方案

* 格式 `MAJOR.MINOR.PATCH`，git **附注标签** `vX.Y.Z`；镜像语义标签与 git 标签同形（`:vX.Y.Z`）。
* **0.x 语义**：`MAJOR=0` 为初始阶段，无对外兼容承诺，不兼容调整可走 MINOR（Semver 惯例）；升 `1.0.0` 的时机由 owner 显式决定。
* **不使用 pre-release 版本**（alpha/beta/rc）：main 即生产、单人使用，无预发布通道需求。

### 版本同步矩阵（一律由 `scripts/release.py` 维护，禁止手改）

| 位置 | 消费方 | 同步方式 |
| --- | --- | --- |
| `VERSION`（根） | 唯一事实来源 | release 脚本写入 |
| `backend/app/main.py` `FastAPI(version=…)` | `openapi.json` 的 `info.version`、API 文档 | 运行时 `_resolve_version()` 读根 VERSION（`APP_VERSION` 环境变量优先；镜像内 `/app/VERSION` 由 Dockerfile COPY） |
| `backend/openapi.json` | CI 契约门禁 `check_openapi.py`（全量比对含 `info.version`） | release 时用钉版 `.venv-openapi` 进程内重导出，**必须与版本变更同 commit** |
| `backend/pyproject.toml` | 无直接消费（不参与构建） | release 脚本替换 |
| `frontend/package.json` + `package-lock.json`（两处） | 构建期注入 `NEXT_PUBLIC_APP_VERSION`（`next.config.js`）→ 设置页「系统信息」展示；lock 不同步会击穿 `npm ci` | release 脚本替换 |
| `ir-cli/pyproject.toml` | `ir --version`（`importlib.metadata`） | release 脚本替换 |

## 2. Bump 规则

按上个 `v` tag 以来的 conventional commits 判定（`release.py --suggest` 自动建议）：

| 级别 | 触发条件 |
| --- | --- |
| **MAJOR** | 不兼容变更：删除既有 API 端点或破坏性改变响应结构（ir-cli/前端无法兼容）、不可逆 DB 迁移（`SKIP_DOWNGRADE` 豁免类）、配置/数据格式破坏性调整；commit 带 `BREAKING CHANGE` 或 `!` 标记 |
| **MINOR** | 向后兼容的功能新增（`feat`：新端点/页面/CLI 命令） |
| **PATCH** | 向后兼容的修复与杂项（`fix`/`chore`/`docs`/`refactor`/`test`/`perf`/依赖升级） |

* 常规**可逆** DB 迁移（CI 强制 downgrade 往返验证）属 MINOR/PATCH，不构成 MAJOR。
* openapi 契约演进是常态，仅「破坏已发布契约兼容性」才 MAJOR——本仓前后端/CLI 同仓同部署，兼容压力低。

## 3. 日期与版本的关系

版本号本身**不含日期**——Semver 表达的是变更幅度而非时间。日期体现在三处：

1. CHANGELOG 条目标题：`## vX.Y.Z - YYYY-MM-DD`；
2. git 附注标签时间戳（`git tag -n` / `git for-each-ref refs/tags`）；
3. `deploy/YYYYMMDD-SHORTSHA` 部署标签。

`vX.Y.Z` 与 `deploy/*` 标签指向同一 commit，镜像同时携带 `:vX.Y.Z` 与 `:sha7`，从版本号可完整追溯上线日期。

## 4. 发布流程

```bash
python3 scripts/release.py --suggest           # 1. 看建议的 bump 类型（只读）
python3 scripts/release.py patch --dry-run     # 2. 预览全部改动 + CHANGELOG 草稿（不落盘）
python3 scripts/release.py patch               # 3. 真跑；推送前交互确认（非交互加 --yes）
```

* **前提**：main 分支、工作区干净、与 origin/main 同步；钉版契约环境 `.venv-openapi/` 存在（缺失时脚本给出重建命令：`python3 -m venv .venv-openapi && .venv-openapi/bin/pip install -r backend/requirements.txt`）。
* **脚本原子完成**：同步 5 处版本文件（含 package-lock 两处）→ 进程内重导出 `openapi.json` → `check_openapi.py` + `gen_response_fields.py --check` 验证 → CHANGELOG 顶部插入新条目 → 单 commit `chore(release): vX.Y.Z` → 附注标签 `vX.Y.Z` → 推送 main + tag。
* **发布提交不经 PR、直接在 main 上打**：仓库以 merge-commit 合并 PR，`v` 标签必须落在 main tip 上，deploy.yml 才能识别「被部署 commit 的语义版本」并给镜像追加 `:vX.Y.Z`；owner 权限直接推送 main（ruleset 对 admin 豁免）。
* **节奏**：手动触发；功能里程碑收口发 MINOR，一批修复后可批量发 PATCH，不要求每次合入都发版。
* **失败恢复**：commit 前失败 → `git restore --staged . && git restore .`；commit 后推送前失败 → `git reset --hard origin/main` 并 `git tag -d vX.Y.Z`。
* 首次发布用 `--initial v0.1.0`（基线摘要条目，此前历史不逐条回溯）。

## 5. 镜像与部署标签

* `deploy.yml` 构建时检测被部署 commit 是否带 `v*` 标签，命中则镜像在 `:sha7`、`:latest` 之外**额外推送 `:vX.Y.Z`**。
* `deploy/YYYYMMDD-SHORTSHA` git 标签机制不变（部署标记，与语义版本正交）。
* 手动 `workflow_dispatch` 回滚/重部署只接受已有镜像 tag，`:vX.Y.Z` 亦可用。
