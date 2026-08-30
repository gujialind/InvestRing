# #259 实施计划 — 提交交易产品选择器：市场标识独立徽章 + title 悬停（核心修复 A+B）

> 本计划源自 2026-08-30 会话中 Claude（session 3cd230c6）对 #259 的评审与实施计划（`/tmp/issue259_plan_run.log`），并经用户确认「先实施 A+B」。范围锁定 Phase 1 核心修复，不含类型筛选增强（D'）与虚拟产品排除（另提 issue）。
> 决策（沿用评审 Q1-Q7 的推荐，用户"先实施 A+B"即按推荐执行）：
> - Q1 核心 A+B：**是**
> - Q2 类型筛选：**本次不做**（#324 已作为独立 issue）
> - Q3 市场形态：**选项行 Badge neutral 徽章；回显 muted 纯文本后缀**
> - Q4 虚拟产品：**本次不动**，另提 issue
> - Q5 E2E 种子 LOF 一码双市场：**是**
> - Q6 data-testid 最小集：**现在加**
> - Q7 PR 策略：**分两 PR**（本 PR = #259 核心修复）

## 目标

修复 `SearchableProductSelect`（提交交易产品选择器）：长名称 LOF 一码多市场记录的市场标识被截断/缺失，场内场外无法分辨。A=市场标识独立 `shrink-0` 元素，B=被截断部分加 `title` 悬停全文。**纯前端改动 + 种子 + E2E，零后端改动。**

## 改动清单

### 1. `frontend/src/components/shared/SearchableProductSelect.tsx`（唯一业务改动文件）

当前选项行（L135-144）与回显（L77-82、L98）需重构。

**选项行**（`items.map` 内，当前 L139-142）拆为三段 flex：
- 名称省：`min-w-0 flex-1 truncate`（仅名称可截断）
- 代码省：`(code)` 改为 `shrink-0 text-muted-foreground` 独立元素（稳定标识不随名称截断）
- 市场省：尾部 `shrink-0` 标识，`market` 非空才渲染，形态 `Badge variant="neutral"`（Q3）
- 行容器加 `title={完整 "名称 (code) · 市场"}`（Q3，B 项）

**选中回显**（L77-82 的 label / L98 的 span）：
- label 拼接：`名称 (code)` + ` · 市场名` 后缀
- 后缀放独立 `shrink-0` span，仅名称部分 `truncate`
- 触发按钮 span 加 `title` 全文本（B 项）

**E2E 定位钩子**（Q6）：选项行加 `data-testid="product-option"` + `data-code` + `data-market`（复刻 platform-option 既有模式）。

**`market` 为空时**：不渲染市场徽章、回显无 `· --` 残留。

### 2. `backend/tests/seed_base.py`（为 E2E 供数据，Q5）

新增 LOF 一码双市场种子（附加式，幂等）：
- `161017.SZ`（CN_EXCHANGE，LOF，confirm_days=0）
- `161017.OF`（CN_OTC，LOF，confirm_days=1）

名称用长名（如「富国中证500指数增强(LOF)A」）以稳定触发截断；维度标签内联给出（参照 `510300.SH` 写法）。

### 3. `frontend/e2e/`（新增/并入 spec）

- 搜 `161017` → 两条选项市场标识（A股场内/内地场外）均可见且文案不同
- 选项行 `title` 含完整「名称 (code) · 市场」
- 选中场外项 → 回显含「内地场外」且带 `title`
- mobile project 复跑（组件共享，自动覆盖）
- 遵循「优雅 skip」惯例（无 161017 种子时 skip）

## 验证

- `npm run build`（tsc+ESLint 门禁，0 error）
- 后端 `pytest`（种子变更回归）
- `npm run test:e2e` 相关 spec
- 视觉规范自查：徽章用 `Badge neutral`，无裸调色板类名、无新增字号/色值

## 边界

- **不做**类型筛选（#324）、**不做**虚拟产品排除、**不 push / 不建 PR / 不发 issue 评论**（这些由编排者处理）
- 完成后 git commit（消息遵循仓库惯例 `fix(...)`，`fixes #259`）
