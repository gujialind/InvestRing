# 实施计划：#161 DateRangePicker 弹层高度超视口修复（双月横排 + 高度约束兜底）

> 目标：任何视口高度下，日期区间弹层的快捷项/日历/「确定」footer 均可达——桌面双月恢复**并排**（规范 §10 本就如此约定，代码偏离），弹层超高时**内部滚动 + footer 常驻**兜底。
>
> **前置状态（已核实）**：
>
> - #154 修复 957c018 已合入（草稿态 + footer「确定」+ 快捷项 flex-wrap），footer 位于弹层最底部是本次不可达的直接载体；
> - `calendar.tsx` L158 `months: "relative flex flex-col gap-4"` 无条件纵排，与 `docs/design/visual-spec.md` §10「桌面双月并排」条款**不符**（d228ebc 定制引入的偏差，非规范变更）；
> - `PopoverContent` 原语（`popover.tsx`）无高度约束；全仓 `PopoverContent` 消费方仅 `date-picker.tsx`（单月，~340px，不在本 issue 范围）与 `date-range-picker.tsx` 两处；
> - `numberOfMonths={2}` 使用方仅 DateRangePicker（TradesContent / SubscriptionsContent / SnapshotsContent 三处，桌面端传 2、移动端传 1），`Calendar` 其余使用方均单月，改动 `months` 样式不影响；
> - `.claude/rules/visual-spec.md` 为指针文件（非全文副本），规范修订只改 `docs/design/visual-spec.md`。
>
> **方案选型（issue #161 已列 A/B/C，本计划选定 A+B）**：B 治本（双月并排，桌面弹层高度 ~700px → ~380px，多数场景不再溢出且回归规范）；A 兜底（视口再矮/移动端仍超高时弹层内部滚动，footer sticky 常驻）。不选 C（移动端改 Drawer/Dialog：形态偏离规范 §10 现行条款，A+B 后无必要，YAGNI）。

---

## 1. 改动地图

| 层 | 文件 | 动作 |
|---|---|---|
| frontend | `src/components/ui/calendar.tsx` | `months` 样式改 `sm:flex-row flex-wrap`，桌面双月并排（B） |
| frontend | `src/components/ui/date-range-picker.tsx` | `PopoverContent` 加高度约束 + footer 改 sticky（A） |
| docs | `docs/design/visual-spec.md` | §10 补「弹层高度约束」条款（A 的形态约定） |

无后端/CLI/DB/依赖改动。三文件、预期 diff < 20 行。

---

## 2. 改动明细

### 2.1 `ui/calendar.tsx` — 双月并排（方案 B）

L158 `months` 类名：

```diff
- months: cn("relative flex flex-col gap-4", defaultClassNames.months),
+ months: cn("relative flex flex-col gap-4 sm:flex-row sm:flex-wrap", defaultClassNames.months),
```

要点：

- `sm:`（≥640px）起横排，与 shadcn 上游默认一致；移动端 `numberOfMonths=1` 本就单月，不受影响；
- `flex-wrap` 保留：视口宽度不足（640~800px 的窄笔记本半屏）时自动回落纵排，回落后弹层变高，由 2.2 的 A 方案兜底滚动；
- **影响面核查（已做）**：`numberOfMonths≥2` 的调用方仅 DateRangePicker；单月调用方（DatePicker、SnapshotsContent 等表单/工具场景）months 容器只有一个子元素，横/纵排无行为差异。

### 2.2 `ui/date-range-picker.tsx` — 高度约束 + footer 常驻（方案 A）

L179-203 两处：

```diff
  <PopoverContent
    align="start"
-   className="w-auto p-0"
+   className="w-auto max-h-[min(calc(100dvh_-_2rem),44rem)] overflow-y-auto p-0"
    onCloseAutoFocus={(e) => e.preventDefault()}
  >
```

```diff
- <div className="flex items-center justify-between gap-2 border-t px-3 py-2">
+ <div className="sticky bottom-0 z-10 flex items-center justify-between gap-2 border-t bg-popover px-3 py-2">
```

要点：

- `max-h-[min(calc(100dvh_-_2rem),44rem)]`：上限取「视口高 − 上下各 1rem 余量」与 44rem（704px）的较小者——桌面 B 方案后弹层 ~380px 天然不触发；移动端（快捷项 2~3 行 + 单月 + footer ≈ 450px）在矮视口触发内部滚动；
- `100dvh`（非 `vh`）：移动端浏览器地址栏收展时动态视口高度，避免 `vh` 偏大仍溢出；
- footer `sticky bottom-0` + `bg-popover`：触发滚动时「确定」常驻弹层底部可见（sticky 作用域即滚动容器 PopoverContent 自身，无需额外包裹）；`z-10` 防止日历 day 按钮 `group-data-[focused]/day:z-10` 聚焦环叠上来；
- `overflow-y-auto` 只加在本组件的 `PopoverContent` 用法上，**不动 `popover.tsx` 原语**——DatePicker（单月）理论上矮视口也可能溢出，但不在 #161 范围，不扩面；若后续需要再提独立 issue；
- 滚动容器内 `autoFocus`（react-day-picker 聚焦首日）行为不变；Radix Popover 对内部滚动无拦截。

### 2.3 `docs/design/visual-spec.md` §10 — 补高度约束条款

「弹层行为」条目（#154 修订段）末尾追加一句：

> 弹层总高以视口为限（`max-h` 取 `min(100dvh − 2rem, 44rem)`）：超高时弹层**内部滚动**，footer（摘要 + 确定）sticky 常驻底部，任何视口下「确定」可达；桌面双月并排（`sm:flex-row`，窄屏 flex-wrap 回落纵排）。

并把「双端」条目中「桌面 `numberOfMonths={2}` 双月并排」标注为 #161 落实（该条款早已存在，本次是代码回归规范，规范文字本身无需改）。

---

## 3. 验证方案

### 3.1 质量门禁

- `cd frontend && npm run lint && npm run build` → 0 error（构建期强门禁）。

### 3.2 视觉验证（WSL2 + Windows Chrome 无头截图，既有流程）

启动本地 dev（`npm run dev`，后端经 ssh-tunnel 或本地），对以下矩阵逐项截图核对（每项开弹层截图 1 张，重点：footer 是否完整可见）：

| # | 视口 | 页面/场景 | 断言 |
|---|---|---|---|
| 1 | 1920×1080 | 调仓页（记录少无滚动条） | 双月**并排**横排，弹层完整可见含「确定」 |
| 2 | 1280×800 | 申赎页（记录少） | 双月并排，弹层完整可见含「确定」 |
| 3 | 1280×600 | 任一筛选页 | 弹层触发 `max-h` 内部滚动，footer sticky「确定」常驻可见可点 |
| 4 | 390×844（移动模拟，UA 走 `/m/`） | 申赎页筛选面板 | 快捷项 8 项全部可见（wrap 换行）+「确定」可见可点；矮屏时内部滚动且 footer 常驻 |
| 5 | 1280×700 + 半屏窄窗（~700px 宽） | 任一筛选页 | 双月 flex-wrap 回落纵排时不破版，滚动兜底生效 |

对应 issue #161 五条验收断言；移动端（#4）如 Windows Chrome 设备模拟与真机渲染有出入，以真机复验为准。

### 3.3 回归核对

- 单选 `DatePicker`（表单内交易日标注场景，如调仓新建/现金修正）开弹层正常（months 样式改动对单月无影响，仍抽 1 项确认）；
- 快照历史页（SnapshotsContent 已接 DateRangePicker）按 #2/#4 视口抽查 1 次。

### 3.4 E2E（可选，不阻断）

`frontend/e2e/` 现有 Playwright 基件：可加 1 条用例「600px 视口打开日期弹层 → 「确定」按钮 boundingBox 在视口内」，防止回归。实施时若 30 分钟内可挂上则带上，否则记录为后续补测项在 PR 说明注明。

---

## 4. 风险与备注

1. **双月并排弹层变宽**（快捷项列 ~130px + 双月 ~560px ≈ 700px）：`align="start"` + 触发按钮位于筛选栏靠左，≥1280px 桌面无遮挡风险；640~800px 窄窗由 flex-wrap 回落（验证矩阵 #5 覆盖）。
2. **sticky footer 在 `overflow-y-auto` + `p-0` 容器内**：无 padding 干扰，`bg-popover` 需覆盖滚动内容——PopoverContent 自带 `bg-popover`，footer 显式同色即可；若滚动条出现导致 footer 右缘与内容右缘错位（ scrollbar 占宽），可接受（滚动条本身即「可滚」暗示）。
3. **`100dvh` 兼容**：目标浏览器为现代 Chrome/Safari（自用工具），dvh 支持无虞；不做 `vh` 降级。
4. **不扩面**：popover.tsx 原语不动（DatePicker 单月场景留观）；移动端 Drawer 形态（方案 C）不做；E2E 可选项不阻断合并。
5. **分支**：`fix/161-daterangepicker-height` 自最新 dev 切出；PR 引用 issue #161，验收断言逐条勾选回贴截图。
