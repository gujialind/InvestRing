# 实施计划：#177 平台选择框搜索（SearchablePlatformSelect）

> 目标：新建共享 `SearchablePlatformSelect` 组件（触发按钮 + Popover + 客户端按 name/code 过滤 + 点选回传），替换全部 10 处平台选择点，并处理评审发现的 R1 回归风险（申赎表单原生 `required` 校验静默丢失）。
>
> **分支/PR 策略**：单分支 `feature/177-platform-select-search`（从最新 `origin/main` 拉出），2 个逻辑 commit，单个 PR（描述含 `fixes #177`）。纯前端改动，无 DB / API / CLI 变更，无新依赖。
>
> **分工（2026-08-22 用户拍板，二次修正）**：Claude Code 负责代码实现（Commit 1 + Commit 2）**和 E2E 测试用例编写**（Commit 3，resume 实施会话补写，它有完整实现上下文最可靠）；编排者 Hermes 负责**执行**测试（lint/build 门禁复跑、Playwright 运行、验收自查清单核对、手动冒烟）与建 PR。
>
> **前置状态（已核实，行号以 main 当前代码为准，实施时以结构定位为准）**：
>
> - 参照组件 `frontend/src/components/shared/SearchableProductSelect.tsx`（#162）：触发按钮 + `Popover` + `Input` + `Check/ChevronDown` 图标（lucide-react），点选即回传并关闭。本组件复刻其交互外壳，但**数据流刻意不同**（见决策 1）。
> - 平台 API `platformApi.list`（`src/lib/api/platform.ts`）仅支持 `page/page_size`，无 keyword——客户端过滤是唯一合理路径；`Platform` 类型（`src/types/platform.ts`）仅 `code/name/platform_type/created_at`，无停用字段。
> - 各调用方均已全量加载平台列表：`usePlatformList({ page_size: 100 })`（TradesContent/SubscriptionsContent）或 `useQuery(["platforms"], platformApi.list({page_size:100}))`（positions/share-change-events/m-positions）。
> - `cn()`（`src/lib/utils.ts`）基于 clsx + tailwind-merge，后传 className 可覆盖默认尺寸类（`h-9` 覆盖 `h-10`、`w-[150px]` 覆盖 `w-full`）。
> - 质量门禁：无单元测试框架（无 vitest/jest）；强制 `npm run lint` + `npm run build`（ESLint + tsc 0 error）；E2E 用 Playwright（`frontend/e2e/`，chromium + mobile 双 project，standalone 生产构建，认证经 `e2e/fixtures/auth.setup.ts` 存 `e2e/.auth/admin.json`）。
> - 视觉规范（`docs/design/visual-spec.md`）：筛选栏控件统一 `h-9` 紧凑档、省略 Label 以 placeholder 表意（§9）；表单对话框内控件 `h-10`（§9）；表单校验反馈的**现存先例**为 toast（positions/share-change-events 均为 `title: "表单校验失败"`，§14 字面要求 inline Alert 但表单提交校验场景事实标准是 toast）。
> - 移动端覆盖路径：`app/m/portfolio/[code]/trades/page.tsx` 与 `.../subscriptions/page.tsx` 是薄壳，复用 `TradesContent/SubscriptionsContent variant="mobile"`——改 shared 组件天然覆盖双端；移动端独立改动仅 `m/positions` 1 处。
> - 全部目标 Dialog 均为 `modal={false}`，且 `SearchableProductSelect`（Popover）已在 TradesContent 提交交易 Dialog 内线上运行（#162）——Popover-in-Dialog 无 z-index/焦点陷阱风险。

---

## 0. 已确认决策（用户拍板，直接采纳，不重新讨论）

1. **方案 A**：新建共享 `SearchablePlatformSelect`，复用 Product 版交互外壳；纯客户端按 name/code 过滤；**组件不内部 fetch**——接收 `platforms: Platform[]` prop（各调用方已持有列表）；本地过滤**省掉 300ms 防抖**（防抖对产品版是网络节流，对本地过滤纯是延迟）。
2. **前置特殊项**（全部平台/同交易平台）用哨兵承载内部状态，固定置顶、不参与过滤；`onChange` 对外回传 `string | null`，点选特殊项回传 `null`，调用方映射回既有语义（`undefined`/`""`）。
3. **现金转移互斥项**保持「可见但禁用」（`isOptionDisabled` 谓词），不过滤掉。
4. **R1 必须处理**：申赎表单平台原生 `<select required>` 替换后浏览器校验失效，须在 `handleSubmit` 补手动校验，并加验收断言。
5. **不引入新依赖**（无 cmdk，用现有 `ui/popover` + `ui/input`）；键盘可达性（R5）为可选增强——其中 **Input 打开自动聚焦**成本为零，直接做；方向键/Enter 导航不做（与 Product 版保持一致，如需另提 issue）。
6. **投资人选择框不纳入范围**（YAGNI）；泛型化抽取不做（等第三个可搜索维度出现再说）。

---

## 1. 改动地图

| 文件 | 动作 | 替换点数 |
|---|---|---|
| `frontend/src/components/shared/SearchablePlatformSelect.tsx` | **新建**共享组件 | — |
| `frontend/src/components/shared/TradesContent.tsx` | 替换筛选栏平台 filter + 表单「交易平台」+ 表单「现金平台」 | 3 |
| `frontend/src/components/shared/SubscriptionsContent.tsx` | 替换筛选栏平台 filter + 表单「交易平台」；**R1**：`handleSubmit` 补平台手动校验 | 2 |
| `frontend/src/app/portfolio/[code]/positions/page.tsx` | 替换非净值资产更新「平台」+ 现金转移「转出/转入平台」（保留互斥 disabled） | 3 |
| `frontend/src/app/portfolio/[code]/share-change-events/page.tsx` | 替换平台选择器（仅平台级事件显示） | 1 |
| `frontend/src/app/m/portfolio/[code]/positions/page.tsx` | 替换非净值资产更新「平台」 | 1 |
| `frontend/e2e/platform-select-search.spec.ts` | **新建** E2E 回归用例 | — |

无 DB 迁移、无新依赖、无 CLI/openapi 变更。`AGENTS.md` 无需更新（无新设计决策，组件可从代码发现）。

**命名勘误（不影响范围）**：issue 称 PC positions 的「交易表单平台」，实际调仓 Dialog（L262-334）无平台字段；指的是**非净值资产更新对话框**的平台选择（L350-364）。计数 3 处不变。

---

## 2. 组件规格：`SearchablePlatformSelect`

### 2.1 签名（props 契约）

```tsx
// frontend/src/components/shared/SearchablePlatformSelect.tsx
"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Platform } from "@/types/platform";

interface SearchablePlatformSelectProps {
  /** 平台全量列表（调用方已加载；组件不内部 fetch） */
  platforms: Platform[];
  /** 选中平台 code；null = 未选/选中前置特殊项 */
  value: string | null;
  /** 点选平台回传 code；点选前置特殊项回传 null */
  onChange: (code: string | null) => void;
  /** 前置特殊项文案（固定置顶、不参与搜索过滤），如「全部平台」「同交易平台」；
   *  value === null 时触发按钮以正常前景色回显该文案 */
  specialOptionLabel?: string;
  /** 无 specialOptionLabel 且 value === null 时的占位文案（muted 色），默认「请选择平台」 */
  placeholder?: string;
  /** 逐选项禁用谓词（现金转移互斥）：禁用项可见但不可点 */
  isOptionDisabled?: (platform: Platform) => boolean;
  /** 触发按钮附加 className（尺寸档：筛选栏传 h-9 档、表单默认 h-10；cn+twMerge 后者覆盖前者） */
  className?: string;
  /** 触发按钮 id，供外层 Label htmlFor 关联（可访问性） */
  id?: string;
}
```

### 2.2 行为矩阵

| 场景 | 行为 |
|---|---|
| 触发按钮回显 | 选中平台 → `{name} ({code})`（`platforms.find(p => p.code === value)`，列表全量故无需 Product 版的名称缓存）；`value` 非 null 但列表中找不到（加载中/异常兜底）→ 显示 code 本身；`value === null` 且有 `specialOptionLabel` → 正常色显示特殊项文案；`value === null` 且无特殊项 → muted 色显示 `placeholder` |
| 打开弹层 | `onOpenChange(true)` 时**重置搜索词为空**（每次打开全量选项，避免残留旧词造成「选项丢失」误判）；Input `autoFocus`（R5 零成本项） |
| 过滤 | `keyword.trim().toLowerCase()`，`name` 或 `code` `includes` 命中即保留（大小写不敏感）；无防抖、同步 `useMemo`；特殊项恒显示不参与过滤 |
| 点选平台 | `onChange(code)` + 关闭弹层 |
| 点选特殊项 | `onChange(null)` + 关闭弹层 |
| 选中标记 | 行首 `Check` 图标：平台行 `p.code === value` 时可见；特殊项行 `value === null` 时可见（同 Product 版 opacity 切换模式） |
| 禁用项 | `isOptionDisabled?.(p) === true`：`aria-disabled` + `opacity-50 cursor-not-allowed`，不挂 onClick；**不过滤、随搜索结果正常渲染** |
| 空态 | 过滤后无平台项（特殊项仍显示）→ 列表区显示「无符合条件的平台」（`py-6 text-center text-sm text-muted-foreground`，对齐 Product 版空态样式） |
| 关闭 | Esc / 点击弹层外（radix Popover 自带）；关闭时搜索词随 `open=false` 重置 |
| 尺寸 | 触发按钮基础类含 `h-10 w-full`（表单档）；筛选栏调用方经 `className` 传 `h-9 w-[150px]`（桌面）/ `h-9 w-full`（移动）；弹层内容固定 `w-80 p-0`、`align="start"`（同 Product 版） |

### 2.3 实现骨架（规格级，实施时可微调）

```tsx
export default function SearchablePlatformSelect({
  platforms, value, onChange,
  specialOptionLabel, placeholder = "请选择平台",
  isOptionDisabled, className, id,
}: SearchablePlatformSelectProps) {
  const [open, setOpen] = useState(false);
  const [keyword, setKeyword] = useState("");

  const kw = keyword.trim().toLowerCase();
  const filtered = useMemo(
    () => kw
      ? platforms.filter((p) =>
          p.name.toLowerCase().includes(kw) || p.code.toLowerCase().includes(kw))
      : platforms,
    [platforms, kw]
  );

  const selected = value ? platforms.find((p) => p.code === value) : undefined;
  const label = selected
    ? `${selected.name} (${selected.code})`
    : value ?? specialOptionLabel ?? placeholder;
  const labelMuted = !selected && !value && !specialOptionLabel;

  const pick = (code: string | null) => { onChange(code); setOpen(false); };

  return (
    <Popover open={open} onOpenChange={(next) => { setOpen(next); if (!next) setKeyword(""); }}>
      <PopoverTrigger asChild>
        <button type="button" id={id} className={cn(
          "flex h-10 w-full items-center justify-between gap-2 rounded-md border border-input",
          "bg-background px-3 py-2 text-left text-sm font-normal ring-offset-background",
          "transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2",
          "focus-visible:ring-ring focus-visible:ring-offset-2",
          className,
        )}>
          <span className={cn("truncate", labelMuted && "text-muted-foreground")}>{label}</span>
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-0">
        <div className="border-b p-2">
          <Input autoFocus value={keyword} onChange={(e) => setKeyword(e.target.value)}
                 placeholder="搜索平台名称/代码" className="h-8" />
        </div>
        <div className="max-h-64 overflow-y-auto p-1">
          {specialOptionLabel && (/* 特殊项固定置顶，不参与过滤 */
            <div /* onClick={() => pick(null)}，Check 在 value===null 时可见，样式同平台行 */ />
          )}
          {filtered.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">无符合条件的平台</p>
          ) : (
            filtered.map((p) => {
              const disabled = isOptionDisabled?.(p) ?? false;
              return (
                <div key={p.code}
                  aria-disabled={disabled || undefined}
                  className={cn("flex items-center gap-2 rounded-sm px-2 py-1.5",
                    disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:bg-muted")}
                  onClick={disabled ? undefined : () => pick(p.code)}>
                  <Check className={cn("h-4 w-4 shrink-0",
                    p.code === value ? "opacity-100" : "opacity-0")} />
                  <span className="min-w-0 flex-1 truncate text-sm">{p.name} ({p.code})</span>
                </div>
              );
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
```

要点：无 react-query、无防抖、无名称缓存（与 Product 版的三个差异点，均是刻意决策）；`type="button"` 必须显式（避免在 `<form>` 内触发提交）。

---

## 3. 分阶段任务（commit 粒度）

### Commit 1 — `feat(frontend): 新增 SearchablePlatformSelect 共享组件 (#177)`

新建 `frontend/src/components/shared/SearchablePlatformSelect.tsx`，按 §2 规格实现。

自查：`npm run lint` 0 error；组件暂不引用（tsc 对未使用导出不报错）。

### Commit 2 — `feat(frontend): 全部平台选择点替换为 SearchablePlatformSelect，补申赎平台手动校验 (#177)`

> 5 个文件、10 处替换 + 1 处校验补充。每个替换点给出**现状结构 → 目标结构**；行号以 main 当前代码为准。

#### 3.1 `frontend/src/components/shared/TradesContent.tsx`（3 处）

新增 import：`SearchablePlatformSelect`（`@/components/shared/SearchablePlatformSelect`）。**保留** `Select` import（状态/类型筛选仍在用）。

**① 筛选栏平台 filter（现 L356-374，shadcn Select + "all" 哨兵）→**

```tsx
<SearchablePlatformSelect
  platforms={platforms}
  value={platformFilter ?? null}
  onChange={(v) => {
    setPlatformFilter(v ?? undefined);
    setPage(1);
  }}
  specialOptionLabel="全部平台"
  className={selectWidth}
/>
```

语义核对：`platformFilter === undefined` ⇒ `listParams.platform_code = undefined` ⇒ 请求不带参（L139），与现状一致；`hasNonDefaultFilter`/`activeFilterCount`/`resetFilters` 均读 `platformFilter`（L170/178/186），无需改。

**② 提交交易表单「交易平台」（现 L642-656，原生 select，无 required）→**

```tsx
<SearchablePlatformSelect
  platforms={platforms}
  value={formData.platform_code || null}
  onChange={(v) => setFormData({ ...formData, platform_code: v ?? "" })}
  placeholder="请选择平台"
  id="platform_code"
/>
```

语义核对：现状无 `required`，空平台提交时 payload `platform_code: formData.platform_code || undefined`（L236）——维持现状，**不新增校验**（后端语义不变）。`Label htmlFor="platform_code"` 保留有效。

**③ 提交交易表单「现金平台」（现 L657-674，原生 select，空选项「同交易平台」）→**

```tsx
<SearchablePlatformSelect
  platforms={platforms}
  value={formData.cash_platform_code || null}
  onChange={(v) => setFormData({ ...formData, cash_platform_code: v ?? "" })}
  specialOptionLabel="同交易平台"
  id="cash_platform_code"
/>
```

语义核对：空值 ⇒ payload `cash_platform_code: ... || undefined`（L237）⇒ 后端按「同交易平台」处理，语义不变。Label 动态文案「现金平台（扣款/到账，可选）」保留。

#### 3.2 `frontend/src/components/shared/SubscriptionsContent.tsx`（2 处 + R1）

新增 import：`SearchablePlatformSelect` + `useUIStore`（`@/stores/uiStore`，R1 toast 通道——该文件当前无 toast 通道）。**保留** `Select` import（状态/投资人/类型筛选在用）。

**① 筛选栏平台 filter（现 L356-374）→** 同 3.1①（`selectWidth` 变量同名同义，`specialOptionLabel="全部平台"`）。

**② 新建申赎表单「交易平台」（现 L474-488，原生 `<select required>` ← R1 风险点）→**

```tsx
<SearchablePlatformSelect
  platforms={platforms}
  value={formData.platform_code || null}
  onChange={(v) => setFormData({ ...formData, platform_code: v ?? "" })}
  placeholder="请选择平台"
  id="platform_code"
/>
```

**③ R1：`handleSubmit`（现 L231-248）补手动校验**——在 `e.preventDefault()` 之后、组装 payload 之前插入：

```tsx
const addToast = useUIStore((state) => state.addToast); // 组件顶部 hook 区新增

// handleSubmit 内：
if (!formData.platform_code) {
  // R1（#177）：原生 <select required> 替换为自定义组件后浏览器校验失效，须手动拦截
  addToast({ type: "error", title: "表单校验失败", message: "请选择平台" });
  return;
}
```

toast 文案对齐 `share-change-events/page.tsx` L162-168 先例（`表单校验失败` + 具体提示）。同表单的投资人原生 `<select required>` 保留不动（范围外，浏览器校验仍有效）。

#### 3.3 `frontend/src/app/portfolio/[code]/positions/page.tsx`（3 处）

新增 import `SearchablePlatformSelect`；`Select` 系 import 检查：替换后该文件不再使用 `Select/SelectTrigger/SelectValue/SelectContent/SelectItem`（3 处全换），**删除对应 import**（lint 会拦未使用 import）。

**① 非净值资产更新对话框「平台」（现 L350-364，shadcn Select + required）→**

```tsx
<SearchablePlatformSelect
  platforms={platforms}
  value={selectedPlatform || null}
  onChange={(v) => setSelectedPlatform(v ?? "")}
  placeholder="请选择平台"
  id="platform"
/>
```

`handleCashUpdateSubmit` 已有手动校验（L128-135 `!selectedPlatform` → toast），保留——required 丢失无回归。

**② 现金转移「转出平台」（现 L440-450）→**

```tsx
<SearchablePlatformSelect
  platforms={platforms}
  value={transferFrom || null}
  onChange={(v) => setTransferFrom(v ?? "")}
  placeholder="选择转出平台"
  isOptionDisabled={(p) => p.code === transferTo}
/>
```

**③ 现金转移「转入平台」（现 L453-463）→** 对称：`value={transferTo || null}`、`onChange={(v) => setTransferTo(v ?? "")}`、`placeholder="选择转入平台"`、`isOptionDisabled={(p) => p.code === transferFrom}`。

语义核对：提交校验（L417-422，空或相同 → toast「请选择不同的转出和转入平台」）已存在且保留；互斥从「SelectItem disabled」平移为「可见但禁用谓词」，行为不变。

#### 3.4 `frontend/src/app/portfolio/[code]/share-change-events/page.tsx`（1 处）

**平台选择器（现 L235-255，仅平台级事件显示，无 required）→**

```tsx
<SearchablePlatformSelect
  platforms={platforms}
  value={formData.platform_code || null}
  onChange={(v) => setFormData({ ...formData, platform_code: v ?? "" })}
  placeholder="选择平台"
  id="platform_code"
/>
```

`handleSubmit`（L159-172）现状只校验 `product_code`，**维持不变**（空平台语义由后端 PLATFORM_NOT_COVERED 等错误兜底，不属本 issue 扩权范围）。`Select` 系 import 若不再使用则删除（检查该文件其他位置——当前仅此处用 Select，替换后删 import）。

#### 3.5 `frontend/src/app/m/portfolio/[code]/positions/page.tsx`（1 处）

**非净值资产更新对话框「平台」（现 L204-219，shadcn Select + required）→** 同 3.3①（`selectedPlatform` 同名状态，`id="platform"`）。手动校验已存在（L76-83），保留。`Select` 系 import 不再使用则删除。

### Commit 3 — `test(e2e): 平台选择框搜索回归用例 (#177)`（Claude 编写，Hermes 执行）

E2E 用例文件 `frontend/e2e/platform-select-search.spec.ts` 由 Claude Code 在实现提交后编写（用例明细见 §4.2）；Hermes 负责执行 Playwright、复跑 lint/build 门禁、逐条核对验收自查清单。

---

## 4. 测试方案

### 4.1 质量门禁（必须全绿）

```bash
cd frontend
npm run lint    # ESLint 0 error（含语义色 token 护栏）
npm run build   # tsc + next build 0 error
```

### 4.2 E2E 用例（Playwright，`frontend/e2e/platform-select-search.spec.ts`）

**数据依赖与跳过策略**：参照 `regression.spec.ts` 的 `gotoFirstPortfolio` 模式——无组合数据则 `test.skip`；平台数 < 2 时互斥用例 skip。平台关键词用例的搜索词**不写死**：先打开弹层读取第一个平台选项文本，取括号内 code 的片段（如 code 前 2 字符）作为搜索词，断言过滤结果均含该 code（大小写不敏感可用小写输入验证）。

| # | 用例 | project | 步骤要点 → 断言 |
|---|---|---|---|
| 1 | 调仓页筛选平台可搜索，且保留「全部平台」 | chromium | 进首个组合 `/portfolio/{code}/trades` → 点筛选栏「全部平台」按钮 → 输入搜索词 → 选项过滤（断言仅剩匹配项）→ 点选 → 触发按钮回显 `name (code)`；重新打开 → 点「全部平台」→ 回显恢复「全部平台」。可用 `page.waitForResponse` 断言列表请求 URL 含/不含 `platform_code=`（评审断言 R3） |
| 2 | 提交交易表单交易平台可搜索、现金平台默认「同交易平台」 | chromium | trades 页 → 「提交交易」Dialog → 交易平台按钮搜索点选 → 回显 `name (code)`；现金平台按钮未操作时回显「同交易平台」，打开可见特殊项置顶 |
| 3 | **R1**：申赎表单未选平台提交被前端拦截 | chromium | subscriptions 页 → 新建申赎 Dialog → 选投资人、填金额、日期（不选平台）→ 提交 → 断言 toast「请选择平台」可见 **且 Dialog 仍打开**（未发出创建请求） |
| 4 | 现金转移互斥项可见但禁用 | chromium | positions 页 → 「平台间现金转移」→ 转出平台选 A → 打开转入平台 → 平台 A 行存在且 `aria-disabled`、点击不生效（弹层不关闭） |
| 5 | 移动端平台选择框可搜索 | mobile | `/m/portfolio/{code}/positions` → 「更新非净值资产」→ 平台按钮 → 搜索 → 点选 → 回显 `name (code)`；另验证 trades 移动页筛选面板（「筛选」折叠面板展开后）平台控件可搜索（覆盖 shared 组件 mobile variant） |
| 6 | 清空搜索词恢复全量 + 无匹配空态 | chromium | 任一平台弹层：输入搜索词后再清空 → 选项恢复全量；输入不可能命中的词（如 `zzz-none`）→ 显示「无符合条件的平台」 |

实施提示：触发按钮是 `<button type="button">`，用文案定位（`page.getByRole('button', { name: '全部平台' })`）；弹层选项用 `getByText` 或弹层容器内 locator；注意 hydration 等待先例（`auth.setup.ts` 的 `__reactProps` 等待模式，fill 前确保水合完成）。

### 4.3 手动冒烟（提交前自查）

PC + 移动双端各过一遍 10 处控件的外观（尺寸档正确：筛选栏 h-9、表单 h-10）、回显、过滤、特殊项、禁用态；重点核对现金平台「同交易平台」与筛选「全部平台」选中后请求参数回归（浏览器 Network 面板）。

---

## 5. 验收自查清单（对照 issue 6 条 + 评审补充 3 条）

| # | 来源 | 断言 | 验证方式 |
|---|---|---|---|
| 1 | issue | 任一平台选择框点击后出现搜索输入框，输入名字或代码可过滤选项（大小写不敏感） | E2E 用例 1/2/5 + 手动全覆盖 10 处 |
| 2 | issue | 调仓交易提交表单「交易平台」「现金平台」支持搜索，选中回显 `name (code)` | E2E 用例 2 |
| 3 | issue | 调仓/申赎列表筛选平台支持搜索，且保留「全部平台」选项 | E2E 用例 1（trades）+ 手动（subscriptions 同控件） |
| 4 | issue | 现金转移转出/转入平台支持搜索，且互斥 disabled 行为不变 | E2E 用例 4 |
| 5 | issue | 移动端对应平台选择框同步支持搜索 | E2E 用例 5 |
| 6 | issue | 清空搜索词恢复全量选项；无匹配时显示空态提示 | E2E 用例 6 |
| 7 | 评审 R1 | 申赎表单未选平台提交时被前端拦截（回归原生 `required` 语义） | E2E 用例 3 |
| 8 | 评审 R3 | 筛选栏选「全部平台」后请求参数不含 `platform_code`；现金平台选「同交易平台」提交时 `cash_platform_code` 为空 | E2E 用例 1（请求断言）+ 手动 Network 核对 |
| 9 | 评审 R4 | 现金转移中被对方选中的平台在列表中可见但禁用 | E2E 用例 4 |

---

## 6. 风险与备注

1. **R1 是本 issue 唯一功能回归点**：SubscriptionsContent `handleSubmit` 当前完全依赖浏览器原生 `required` 拦截空平台（文件注释「required/min 已拦，双保险」为证）。漏掉 §3.2③ 则空平台直达后端报 422。Commit 2 必须含此改动，验收断言 7 是其防线。
2. **校验反馈通道**：SubscriptionsContent 当前无 `useUIStore`/toast 引用，需新增 import；文案对齐 share-change-events 的「表单校验失败」先例（visual-spec §14 字面要求表单校验走 inline Alert，但表单提交校验的事实标准是 toast，positions/share-change-events 均如此；保持与相邻代码一致，不在本 PR 扩权整改）。
3. **未使用 import 清理**：positions（PC）/share-change-events/m-positions 三处替换后 `Select` 系组件不再使用，须删 import——`npm run lint` 会拦截遗漏。TradesContent/SubscriptionsContent 的 `Select` 保留（其他筛选项在用）。
4. **行为对齐边界（不改语义）**：TradesContent 表单「交易平台」现状无 `required`、空值提交为 `undefined`，维持现状不加校验；share-change-events 平台选择器现状无前端校验，维持不变。本 PR 只换控件形态，不收紧任何校验口径。
5. **Popover-in-Dialog**：目标 Dialog 均为 `modal={false}`，且 Product 版（#162）已在同形态 Dialog 内线上运行，无焦点陷阱/z-index 风险；实施时若遇弹层被 Dialog 遮挡，先核对是否误开了 `modal`。
6. **搜索词重置策略**：本计划定为「关闭弹层即清空搜索词」（每次打开全量），与 Product 版「保留关键词」不同——平台列表小、打开成本高场景不存在，重置更可预期；验收断言 6 不受影响（断言针对手动清空）。
7. **E2E 环境依赖**：用例需运行环境有 ≥1 组合与（用例 4）≥2 平台；按 `regression.spec.ts` 先例无数据 skip，不在 CI 造数据（E2E 跑在既有 dev 数据面上的前提不变——若 CI 环境数据面变化导致 skip，属可接受降级，手动冒烟兜底）。
8. **不做清单（防范围蔓延）**：投资人选择框不纳入；组件不泛型化；Product 版不回改（防抖/懒加载/名称缓存保留）；方向键导航不做（如需要另提 issue）；后端 platform API 不加 keyword。
