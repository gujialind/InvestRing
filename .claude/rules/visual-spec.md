---
paths:
  - frontend/**
---

# 前端视觉规范（issue #127）

所有 frontend 改动必须遵循 `@../../docs/design/visual-spec.md`（完整规范，写 UI 前阅读）。要点：

- **语义色彩 token**：用 `--color-gain/loss/success/warning/destructive` 及 `-soft` / `-foreground` 变体；禁止 `text-red-500` 等调色板裸类名（ESLint 已强制）。
- **红绿专属涨跌**：`text-gain` / `text-loss` 只用于涨跌数值（经 `getReturnColorClass` / `getReturnBgClass`）；badge 状态色用 `success` / `warning` / `destructive` / `neutral` variant，永不用 gain/loss。
- **图表颜色**：走 `src/lib/colors.ts`（`CHART_COLORS` / `CHART_OTHER` / `NAV_LINE`），禁止组件内裸 hex。
- **数字格式**：走 `src/lib/utils.ts` 格式化函数（`formatCurrency` / `formatShares` / `formatNav` / `formatPercent`），禁止组件内 `toFixed`。
- **字号 4 级**：页面标题 24 / 分区标题 18 / 正文 14 / 辅助 12。
- **组件复用红线**：优先 `src/components/ui` + `src/components/shared`，禁止手写重复件（badge / dialog / toast 先查现成组件）。
- **交互反馈**：加载态用按钮内 `Loader2` 或区块 spinner；操作结果用 toast、表单校验用 inline Alert；危险操作统一 `AlertDialog` 确认。
