# InvestRing 前端视觉规范（visual-spec）

> 轻量活规范（issue #127）：**代码是唯一事实来源**——语义 token 见 `frontend/src/app/globals.css`，图表色板见 `frontend/src/lib/colors.ts`，状态映射见 Badge variant 与 `getStatusBadgeVariant()`。本文只记录**读代码拿不到的决策与理由**，以及跨文件的一致性约定。配色色值即「配色方案 v1」，任何改动须先改本文与 token，再改组件。

---

## 1. 色彩语义

### 1.1 核心决策（拍板项，勿推翻）

1. **红绿专属涨跌（红涨绿跌，中国市场惯例）**。`text-gain` / `text-loss` 及其 `-soft` / `-foreground` 变体**只允许**由 `getReturnColorClass` / `getReturnBgClass`（`lib/utils.ts`）或显式的涨跌语义输出；**badge 状态色永远不许用 gain/loss token，反之亦然**。涨跌另有 `+/-` 符号兜底（`formatReturnRate`/`formatPercent` 自带符号），颜色不是唯一信息通道（WCAG 1.4.1）。**资金流向不属涨跌语义**——现金扣款/到账等流入流出禁用 gain/loss token，金额用 `text-foreground` + `+/-` 符号表意（见 §8 结对行）。
2. **双红分离**——「涨红」与「异常红」是两种不同的红：

   | | 涨红 gain | 异常红 destructive |
   |---|---|---|
   | 色相 | 朱红 5°（偏橙、暖） | 绛红 348°（偏品红、冷） |
   | 使用边界 | 只用于**裸数值/图标**（涨跌幅、盈亏额） | 只用于**带文字标签的载体**（badge、按钮、错误提示），永不单独给数字着色 |

   二者从不出现在同一上下文；绛红永远伴随「失败/异常」文字，不靠颜色单独表意。
3. **success ≠ 绿**。绿色被「跌」独占后，完成/确认语义移交**靛蓝 `#2B5CD7`，并兼任品牌主色 primary**（链接、主按钮、focus 环同源）。完成态是系统里出现频率最高的状态，让默认观感就是「一切正常」，减少色彩噪音。
4. **cancelled / closed / draft / 停用 → neutral 灰 badge**。用户主动撤销 ≠ 系统异常，不再用红。
5. **dark mode 暂缓**：token 已写 light + dark 双套预案值（下同），但代码不启用暗色；启用前必须实测对比度（当前 dark 值为同构推算，未实测）。

### 1.2 语义色 token 色值表（配色方案 v1）

> 对比度为对 light 页面底（白卡）的近似值。主色全部落在 5.1–6.0:1 区间（14px 正文数字直用合规）；foreground 对各自 soft 底全部 ≥6.5:1。

#### 涨跌（金融方向色，专属数值场景）

| Token | 用途 | 色名 | Light | Dark 预案 |
|---|---|---|---|---|
| `--color-gain` | 上涨数值、正向收益 | 朱红 | `#CF3526` hsl(5,69%,48%) ≈5.1:1 | `#F0735F` hsl(8,83%,66%) |
| `--color-gain-soft` | 涨相关浅底（高亮行、盈亏卡片底） | 浅朱 | `#FBEBE8` hsl(9,70%,95%) | `#3B2420` |
| `--color-gain-foreground` | gain-soft 上的文字 | 深朱 | `#A02718` hsl(7,74%,36%) | `#F5A89B` |
| `--color-loss` | 下跌数值、负向收益 | 松绿 | `#177245` hsl(150,66%,27%) ≈6.0:1 | `#3FB97F` hsl(151,49%,49%) |
| `--color-loss-soft` | 跌相关浅底 | 浅松 | `#E6F2EB` hsl(125,32%,93%) | `#1E3A2E` |
| `--color-loss-foreground` | loss-soft 上的文字 | 深松 | `#0F5C36` hsl(150,72%,21%) | `#8FD9B4` |

#### 状态色（业务状态语义，禁用于涨跌数值）

| Token | 用途 | 色名 | Light | Dark 预案 |
|---|---|---|---|---|
| `--color-success` | 完成/确认/启用；**兼品牌主色 primary / ring** | 靛蓝 | `#2B5CD7` hsl(223,68%,51%) ≈5.8:1 | `#7FA3F0` |
| `--color-success-soft` | 成功态 badge/提示底 | 浅靛 | `#E8EEFA` hsl(220,64%,95%) | `#22304F` |
| `--color-success-foreground` | success-soft 上文字 | 深靛 | `#1D47B0` hsl(223,72%,40%) | `#A8C2F5` |
| `--color-warning` | 待定/进行中 | 赭珀 | `#96620A` hsl(38,88%,31%) ≈5.2:1 | `#E5AC4A` |
| `--color-warning-soft` | 待定 badge/提示底 | 浅珀 | `#FBF3E2` hsl(41,76%,94%) | `#3D3020` |
| `--color-warning-foreground` | warning-soft 上文字 | 深珀 | `#7C4A03` hsl(35,95%,25%) | `#EBC88A` |
| `--color-destructive` | 异常/失败文字、危险按钮底 | 绛红 | `#C22745` hsl(348,67%,46%) ≈5.7:1 | `#EE6B80` |
| `--color-destructive-soft` | 失败 badge 底、错误提示底 | 浅绛 | `#FAE8EC` hsl(347,64%,95%) | `#42242C` |
| `--color-destructive-foreground` | destructive-soft 上文字（solid 危险按钮上的文字用纯白 `text-white`） | 深绛 | `#8F1A33` hsl(347,69%,33%) | `#F2A3B1` |

**选色逻辑（为什么不是正红/草绿/正黄）**：涨红取朱红（5° 偏橙）——正红刺眼且与错误红同色相，朱红是账房/印章的传统「喜色」，69% 饱和度压住攻击性；跌绿取松绿（150°、27% 低明度）——鲜绿廉价感重且与「成功绿」国际惯例撞车；warning 压成赭珀（31% 明度）——正黄在白底上对比度无法达标（amber-500 仅 ~2:1），深琥珀棕是可读性达标的最浅解；绛红偏品红 17°——与朱红并置冷暖可辨，且品红向在国际上更常用于 error，双重线索。

**明度三轨**：① 信号主色统一 L 27–51% / 对比度 5–6:1（红绿并排视觉重量拉平）；② soft 底统一 L 93–95%（只给色相暗示，不抢内容）；③ soft 上 foreground 统一 L 21–40%，对底 ≥6.5:1。Dark 预案即三轨反转（主色 L 49–66%、soft 深色底、foreground 提浅），启用时按轨换算即可，不需重新设计。

### 1.3 状态 → Badge variant 映射

`badge.tsx` variant 全集：`default` / `secondary` / `success` / `warning` / `destructive`（soft 形态）/ `neutral` / `outline`。业务状态统一经 `getStatusBadgeVariant()`（`lib/utils.ts`）映射，禁止各页面自行发明状态色：

| 业务状态 | variant | 示例场景 |
|---|---|---|
| confirmed / active / success / passed / 启用 | `success` | 已确认交易、活跃组合、成功任务 |
| pending / running / partial_success / 在途 | `warning` | 待确认申赎/trade、跨天转移在途、运行中任务 |
| failed / error | `destructive` | 失败任务、数据缺失告警、校验未通过 |
| closed / draft / cancelled / 停用 | `neutral` | 已关闭组合、草稿、已撤销、禁用 |
| （操作型危险按钮，非 badge） | solid `bg-destructive text-white` | 删除、关闭组合等确认按钮 |

**无状态语义的标识**（买卖方向、管理员角色、资产名目 chip）不许占用状态色：方向/角色用「neutral badge + 彩色小圆点」或 `default` variant，圆点色取自 `lib/colors.ts`（见 §2）。

### 1.4 中性色体系（蓝灰底，冷静/可信）

| Token | 用途 | Light | Dark 预案 |
|---|---|---|---|
| `--background` | 页面底 | `#FFFFFF`（现状；目标值 `#F7F8FA` hsl(220,23%,97%)，随后续主题切换统一调整） | `#0F1420` |
| `--card` / `--popover` | 卡片/浮层底 | `#FFFFFF` | `#171E2C` |
| `--muted` | 次级底、neutral badge 底、hover 底 | hsl(210,40%,96.1%)（目标 `#EFF1F6`） | `#232B3D` |
| `--border` / `--input` | 边框、分隔线 | hsl(214.3,31.8%,91.4%)（目标 `#E3E7EF`） | `#2B3448` |
| `--foreground` | 一级文字 | hsl(222.2,84%,4.9%)（目标 `#1A2333` hsl(218,32%,15%) ≈15.9:1） | `#E9EDF5` |
| `--color-foreground-secondary` | 二级文字（表头、标签） | `#5A6577` hsl(217,14%,41%) ≈5.9:1 | `#A6B0C6` |
| `--muted-foreground` | 三级文字（12px 辅助、占位符） | hsl(215.4,16.3%,46.9%)（目标 `#64708A`，≈5.0:1，为 12px 辅助文字守 4.5 底线，**禁止再浅**） | `#8A94AB` |
| `--primary` / `--ring` | 主按钮、链接、选中态、focus 环 | = success `#2B5CD7` | `#7FA3F0` |

> 中性色现状值与配色方案目标值有出入的，以「目标值」为演进方向渐进收敛，不在 #127 一次性切换。层级策略：页面灰底 → 白卡浮起 → 边框轻勾勒，三级明度差小、扁平金融风；文字三级 15/41/47% 明度。

### 1.5 护栏（ESLint）

`eslint.config.mjs` 内置 `no-restricted-syntax`（error）：禁止 `(text|bg|border)-(red|green|yellow|blue|amber|emerald|orange|purple|indigo|pink|teal|cyan)-<数字>` 调色板类名（含字符串字面量与模板字符串）。新增颜色需求一律先加语义 token。**豁免清单**：当前无豁免；确需豁免时在代码处加 `eslint-disable-next-line` 并在本节逐条登记（位置 + 理由）。

---

## 2. 图表色板（`lib/colors.ts` 唯一来源）

基于 **Okabe-Ito 色盲安全色板**改造，主动避开 gain 朱红（5°)、loss 松绿（150°)、destructive 绛红（348°）三个已占用色相，饼图切片不会被误读为涨/跌/异常。**组件内禁止出现 hex 字面量**；recharts / 内联 style 等必须用 hex 的场景一律从 `lib/colors.ts` 取：

| 导出 | 值 | 说明 |
|---|---|---|
| `CHART_COLORS[0]` C1 靛蓝 | `#2F5FD0` | 第一序列色；与品牌/success 同色相是刻意的（品牌一致性） |
| `CHART_COLORS[1]` C2 琥珀金 | `#E8A33D` | |
| `CHART_COLORS[2]` C3 天蓝 | `#56B4E9` | Okabe-Ito 原色 |
| `CHART_COLORS[3]` C4 堇紫 | `#7E69D8` | |
| `CHART_COLORS[4]` C5 玫紫 | `#CC79A7` | Okabe-Ito 原色 |
| `CHART_COLORS[5]` C6 赭橙 | `#C9762E` | 与 C2 靠明度（57% vs 48%）+ 饱和度区分 |
| `CHART_COLORS[6]` C7 灰蓝 | `#8A97AC` | 低饱和，**专供「其他」合并项**（`CHART_OTHER`） |
| `CHART_COLORS[7]` C8 深灰蓝 | `#4A5578` | 备用第 8 色 / 次数据线 |
| `NAV_LINE` | = C1 | 净值曲线主线恒为靛蓝，**不用红绿**；涨跌靠坐标轴数值与 tooltip 的 `text-gain/loss` 表达 |
| `ASSET_TYPE_COLORS` | 股票=C1 / 债券=C4 / 黄金=C2 / 现金=C7 / 在途=C3 / 其他=C8 | 饼图与持仓分区共用（`lib/allocation.ts` 消费） |
| `TRADE_DIRECTION_COLORS` | buy=C1 / sell=C6 | 仅用于买/卖方向小圆点，不表达涨跌 |

**色盲友好性（如实说明）**：Deuteranopia/Protanopia 下 C1↔C4、C2↔C6 会趋近，靠 ≥7% 明度差与图例位置兜底；**超过 6 类必须合并为「其他」（C7），这是规范条目而非建议**。Tritanopia（极罕见）下全体可区分。

---

## 3. 数字格式

**金融数字必须走 `lib/utils.ts` 格式化函数，禁止组件内 `toFixed` / 手写千分位**（占比例外见 §4）：

| 数据类型 | 函数 | 规则 |
|---|---|---|
| 金额 | `formatCurrency` / `formatCompactCurrency`（概览大字） | 千分位 + 2 位小数 + `¥` |
| 份额 | `formatShares` | 固定 2 位小数，不带货币符号（勿用 formatCurrency 代替） |
| 净值/价格 | `formatNav` | 固定 4 位小数，不带 `¥` |
| 精确对账金额 | `formatAmount4` | 4 位小数，仅用于与后端/CLI 对账场景 |
| 百分比/收益率 | `formatPercent` / `formatReturnRate` | 默认 2 位小数、自带 `+/-` 符号 |
| 表格数值单元格 | `number-cell` utility（`text-right font-mono tabular-nums`） | 右对齐 + 等宽数字 |
| 无效值 | 各函数 `fallback` | 统一回显 `--`，不显示 `NaN` / `null` |

## 4. 占比精度分层

- **行级占比 1 位小数**：一律经 `largestRemainderPercents`（最大余数法，issue #99），全部行加总恒为 100.0%；禁止各处自行 `toFixed(1)`（会产生 ±0.1%×n 漂移）。
- **分区头/聚合占比取整**：分区头、chip 合计由行级占比**加总后取整**，不再独立计算，保证同分区口径一致（issue #114）；名目 chip 合计恒显示，即使只有一行。
- 饼图图例直接展示行级加总的 1 位小数值（`buildAllocation` 输出），与分区头严格自洽。

## 5. 字号四级

| 级别 | 规格 | Tailwind | 用途 |
|---|---|---|---|
| 页面标题 | 24px / 600 / 1.3 | `text-2xl font-semibold` | page header；金额大字强调用 `amount-large`（同为 24px），不再新造规格 |
| 分区标题 | 18px / 600 / 1.4 | `text-lg font-semibold` | 卡片标题、持仓分区头 |
| 正文 | 14px / 400 / 1.6 | `text-sm` | 表格、表单、正文数值 |
| 辅助 | 12px / 400 / 1.5 | `text-xs` | 标签、时间戳、secondary 信息 |

配套规则：数值一律叠加 `number-cell`；**禁用 text-base/lg 之外的中间档**——`text-base`/`text-xl`/`text-3xl` 及 `text-[Npx]` 任意值属违规存量，后续改动页面时顺手收敛（本规范不强制一次性清零）。

## 6. 双端差异约定

- **同一份语义，两套壳**：移动端 `/m/` 薄壳页 + `MobileLayout`，业务内容走 `components/shared/` 共享组件（`variant: "desktop" | "mobile"` + `basePath` 适配）；颜色、数字格式、占比精度**双端完全一致，不允许端侧各自着色**。
- 布局差异只体现在：移动端网格列数更少（如统计卡 `grid-cols-2`）、表格优先改卡片列表、操作按钮收进图标/抽屉；**不发明移动端独有的色彩或字号**。筛选栏 / 日期区间 / 分页三类控件的端侧形态差异分别见 §9 / §10 / §11，本节只定原则。
- 新增共享组件时默认双端可用；确需端侧独立组件时放 `components/mobile/` / `components/desktop/`，但仍消费同一套 token 与格式化函数。

## 7. 间距 / 圆角 / 阴影体系

- **圆角**：统一走 `--radius` 派生档位——卡片/对话框 `rounded-lg`、输入与按钮 `rounded-md`、badge/chip/状态点 `rounded-full`、checkbox `rounded-sm`（基件规格登记见 §13）；禁用 `rounded-[Npx]` 任意值。
- **阴影**：扁平金融风，**卡片一律无投影**，靠「页面底 → 白卡 → 边框」三级明度差分层；投影仅用于浮层例外——Toast / 下拉 / Popover 用 `shadow-lg`，模态遮罩不动卡片本体。
- **内边距**：卡片内容桌面 `p-6`（CardContent 默认）、移动 `p-3`；区块间距桌面 `space-y-6`/移动 `space-y-4` 为既有惯例，新页面沿用，禁用 `p-[Npx]`/`gap-[Npx]` 任意值。

## 8. 表格规范

- **数字列右对齐 + `number-cell`**（等宽 tabular-nums），文本列左对齐，操作列右对齐；列表头与数据列对齐方式一致。
- **表头**：`text-muted-foreground` 常规字重，不加底色、不加粗（层级靠字号与文字色，不靠底纹）。
- **斑马纹**：不用。行分隔靠 `border-b`，hover 行 `hover:bg-muted/50` 足够表达可点行。
- **空态**：表体空时表下方居中 `text-muted-foreground` 文案（或 `EmptyState` 组件），不渲染空表壳外的额外颜色。空态变体登记：① 数据空（默认）；② 筛选无结果——文案「无符合筛选条件的记录」+ 内嵌「重置筛选」入口（见 §9）；③ 无权限——文案「无权限访问本页」+ 返回入口按钮（`EmptyState` action 位）。
- **加载态**：表体区域居中 `Loader2 animate-spin` + `text-muted-foreground`，不清空表头。此为首次全量加载形态；筛选/翻页等局部刷新的加载态见 §14。
- **主次双行单元格**（#124 起）：单元格允许「主行 + 次要行」复合结构——主行 `text-sm` 正文色，次行 `text-xs text-muted-foreground`（§5/§1.4 既有档位，不新造）；适用场景登记：name + code、产品名 + 市场后缀。双端一致均渲染双行，移动端不裁剪次行。下拉选项内不用双行——用单行 `name (code)`（LOF 附市场后缀，如 `name (code · 场内)`），与既有表单下拉先例一致。
- **结对行（父子行）**（#126 起）：成组记录（基金腿 + 现金腿）主行正常渲染；子行首列缩进一档（`pl-8`）、整行 `bg-muted/50`、内容降一档 `text-xs`（数值仍右对齐 `number-cell`）。主行去下边框（`border-b-0`）使主+子视觉成组，子行保留下边框作组分隔。操作按钮只在主行，子行不单独响应 hover/点击。子行文案模板：「现金扣款 · 平台名」/「现金到账 · 平台名」（中点 `·` 分隔）；落单现金行：「现金 · 业务来源」（如「现金 · 申购确认」）。**子行金额禁用涨跌色**（§1.1）——扣款 `-`、到账 `+` 符号表意，`text-foreground`；符号由展示层按 `trade_type` 推导，不回写数据。

## 9. 筛选栏规范（filter bar）

> 流水类列表页（申赎/调仓/快照等）的标准配置，全站首个落地为 #125/#126。本节只定跨页一致决策，控件本身读 `components/ui/`。

- **容器**：置于表格上方、与表格同卡片内容区顶部，不单独卡片包裹；横向 `flex flex-wrap`、控件间距 `gap-2`，与下方表格的间距走 §7 区块档位。
- **控件尺寸**：筛选栏控件统一紧凑档 `h-9`（Select/Input/日期触发按钮同高）；表单对话框内仍为 `h-10`，两档不混用。
- **标签**：筛选栏省略 `Label`，以 placeholder 表意；placeholder 统一「全部 + 维度名」（全部状态/全部平台/全部产品）。默认有值的筛选（如"最近 1 年"）显示实际值而非 placeholder。
- **控件排序**：全站统一——时间区间 → 状态 → 实体维度（投资人/平台/产品）→ 类型；多页并存时顺序一致。
- **生效方式**：变更即时查询，不设「查询」按钮；文本输入类防抖 300ms，下拉/日期选择即时生效。
- **重置**：单项清空用控件自带清除件（如 date-picker 的 X 先例）；存在非默认筛选时，筛选行末尾出现「重置」ghost 按钮，点击恢复默认筛选集。
- **激活提示**：桌面端控件值即提示，不额外加徽标；移动端「筛选」入口按钮带激活计数 Badge（`default` variant——纯计数无状态语义，§1.3）。
- **移动端形态**：筛选控件收进「筛选」折叠面板，不常驻平铺；展开后纵向堆叠 `grid-cols-1`。
- **筛选无结果空态**：见 §8 空态变体②——文案「无符合筛选条件的记录」+ 内嵌「重置筛选」入口。

## 10. 日期区间选择器（date-range-picker）

> #125 新建 `components/ui/date-range-picker.tsx`（Calendar `mode="range"`），#126 复用。单选 DatePicker 已定先例（outline 触发按钮 + CalendarIcon + 占位 `text-muted-foreground` + X 清空 + 交易日标注）继续有效，本节只定区间场景的新增决策。

- **触发按钮**：继承单选先例；区间文案 `YYYY-MM-DD ~ YYYY-MM-DD`（§12），移动端不换行、溢出省略；桌面端截断时悬停可见完整文案（原生 `title`）。
- **快捷选项**：桌面置日历左侧竖排文本按钮列表，移动端置顶部 `flex-wrap` 换行完整显示（#154 修订：横向滚动在 Popover 内被 flex 布局撑破失效，换行为确定性形态）；选中态 `bg-success-soft text-success-foreground font-medium`（primary 同源 soft 底，§1.2）。快捷项清单由业务定义（如本月/最近 1 年），规范只管形态。联动规则：手动改动区间后，与某快捷项区间完全一致则保持其选中，否则解除全部快捷项选中态。
- **区间选中配色**：起止日 solid `bg-primary` 白字，中间区间底 `bg-success-soft`——不加新 token（primary = success 同源，§1.1 决策 3）。
- **弹层行为**（#154 修订）：弹层内选择为**草稿态**（手选与快捷选项均只填草稿、不关弹层），底部 footer 显示草稿摘要（`起 ~ 止 · 共 N 天`），点「确定」提交并关闭；点弹层外区域关闭 = 放弃草稿。单日区间 = 首击同一日即得 `{D,D}` 草稿，确定提交；草稿态再点同一日 = 清空草稿（react-day-picker v10 `addToRange` 语义）。清空只靠触发按钮 X，弹层内不重复造清空件。
- **双端**：桌面 `numberOfMonths={2}` 双月并排，移动 `numberOfMonths={1}` 单月。
- **交易日标注边界**：筛选场景**不启用** `showTradingDays`（历史区间无交易日语义）；交易/事件录入场景仍用单选 DatePicker 并标注交易日。

## 11. 分页规范

> 随筛选栏引入（#125/#126），此前全站列表均为单页全量拉取。翻页/筛选触发的局部加载态见 §14。

- **桌面形态**：页码列表——总页数 ≤7 全显，>7 折叠为「首末页 + 当前页 ±1 + 省略号」；右侧每页条数切换（20/50/100，默认 20）。
- **移动端形态**：简化为「上一页 / 第 x / N 页 / 下一页」，无页码列表与条数切换。
- **总数**：「共 N 条」`text-xs text-muted-foreground`，置于分页控件左侧。
- **位置**：表格下方整行右对齐（与操作列对齐惯例一致，§8）。

## 12. 文案格式惯例

- **日期**：统一 `YYYY-MM-DD`（`formatDate`）；带时分秒用 `formatDateTime`；相对时间（今天/N 天前）仅限通知等弱精确场景（`formatRelativeDate`）。
- **百分比**：自带 `+/-` 符号（`formatPercent`/`formatReturnRate` 默认 showSign），禁止手工拼 `+`；负号由数值自带。
- **金额**：带 `¥`、千分位、2 位小数；概览大字可用 `formatCompactCurrency` 的万/亿紧凑格式（`¥X.XX 万` / `¥X.XX 亿`），表格内不用紧凑格式。
- **空值占位**：统一 `--`（各 format 函数 fallback），禁止 `N/A`、`null`、空字符串上屏。
- **单位**：份额数值后带「份」、金额不重复写「元」（`¥` 已表意）；图表 tooltip 中金额可带「元」补语义。

## 13. 组件复用红线

- 新 UI **先查 `components/ui/`（基件）与 `components/shared/`（业务件）**，能复用不新造；状态徽标一律 `Badge` + variant（#127 的 9 处手写 badge 收敛为首个执行案例），禁止再出现 `inline-flex items-center rounded-full … bg-*-100 text-*-800` 手写件。
- 双端页面优先 `components/shared/` + `variant`，只有布局本质差异才拆 `components/mobile/` / `components/desktop/`。
- 弹窗一律走 `Dialog` / `AlertDialog` 基件；提示一律走 `Alert` / toast，不自绘浮层。
- **待建基件登记**（规格已定、随首个使用页面落地；未建前禁止手写同功能件）：`checkbox`（#146 首个使用，shadcn 基件，`rounded-sm`、选中态 `bg-primary`）、`date-range-picker`（#125，形态见 §10）、`pagination`（#125/#126，形态见 §11）。

## 14. 交互反馈模式

- **加载态二选一**：区块级 = 居中 spinner（`Loader2 animate-spin` + muted 文案，用于表格/卡片/整页加载）；按钮内 = `Loader2` 替换前缀图标 + `disabled`（用于提交/确认/同步等动作）。**现状以按钮内为主**，新代码动作类加载一律按钮内，区块级仅限首次数据加载。
- **局部加载态**（筛选变更/翻页等局部刷新，#125/#126 起）：保留旧数据，表格容器 `opacity-50` + 右上角 `Loader2` 小 spinner；不切换为空态或区块级 spinner，避免闪烁与布局跳动。首次进入页面的全量加载仍走区块级 spinner（§8）。
- **操作区按钮层级**：每卡片/区块主操作唯一（`default` primary solid），其余 `outline`/`ghost`；危险操作与主操作分区放置，不与主操作并排。
- **错误提示分工**：操作结果（增删改/同步/确认的成败）用 **toast**（success/error/warning/info 四型，映射 success/destructive/warning/success 色系，info 不单独设色）；表单校验、数据完整性、阻断性提示用 **inline Alert**（`default` / `destructive` 两 variant；校验通过/警告用 success/warning 的 `bg-*-soft` + `border-*/30` 组合，不新增 Alert variant）。
- **后台任务进度**（sync-job 类，#146 起）：进行中 = 状态 Badge（`running`→`warning`，§1.3）+ `Loader2` + 文案的行内区块；不引入 Progress 条组件（任务无可靠百分比，YAGNI）。终态反馈仍走上述 toast 分工，页面数据随之刷新。
- **危险操作**（删除、关闭组合、强制操作）统一 `AlertDialog` 二次确认，确认按钮 solid `bg-destructive text-white`；普通确认走 `default`（primary 靛蓝）。
- **破坏性操作两段式确认**（dry_run → confirm，#146 起）：第一步预览 AlertDialog 列出影响范围，文案模板「将删除 X 张快照（YYYY-MM-DD ~ YYYY-MM-DD），此操作不可恢复」；确认按钮沿用 solid `bg-destructive text-white`；拿不到预览结果时禁止直接执行。

## 15. 图表表达规范

- **饼图扇区从大到小排序**（资产分布即按市值降序），色板按 `CHART_COLORS` 顺序消费；**超过 6 类必须合并为「其他」**（`CHART_OTHER` 灰蓝），这是规范条目而非建议。
- **图例位置**：环形图左图右例（移动端上下堆叠），图例 = 色点 + 名称 + 占比（1 位小数，§4）；不单独发明图例样式。
- **tooltip**：金额 `${formatCurrency(value)}`（可带「元」补语义）、净值 `formatNav`、占比 1 位小数；tooltip 内涨跌数值用 `text-gain`/`text-loss`，图表元素本身（线/柱/扇区）永不用涨跌色。
- **折线**：净值主线恒 `NAV_LINE`（C1 靛蓝）、无数据点圆点（`dot={false}`）、参考线用 `CHART_OTHER` 灰蓝虚线；多序列按 C1→C8 顺序取色。

## 16. 图标着色

- 图标默认继承文字色（不加颜色类）；需要语义时与同行文字共用同一 token：成功 `text-success`、警告 `text-warning`、失败 `text-destructive`、涨跌图标随数值走 `getReturnColorClass`。
- 状态指示小圆点（通知级别、交易日标记、方向标识）用对应 token 的 solid 色（`bg-success` / `bg-warning` / `bg-destructive`）或 `lib/colors.ts` 分类色，不用 `-soft`。

## 17. Dark mode 启用条件（暂缓）

token 已备双套值，启用前必须完成：① 实测全部 dark 预案值对比度（当前为同构推算）；② 存量 `slate/gray` 中性类名与任意值色（`[#xxx]`）清理；③ 图表色板暗色适配评审。未满足前禁止在代码中加 `dark` 类或 `dark:` 变体。

## 18. 存量债与迁移策略

- 本规范落地时已完成：语义 token、Badge variant、盈亏色函数、图表色板、全部 `(text|bg|border)-调色板-数字` 类名清零（#127）。
- 已登记、渐进收敛的存量：中间档字号（§5）、`text-[Npx]` 等任意值（29 处）、`slate/gray` 中性类名、中性色目标值切换（§1.4）、快照页原生 `<input type="checkbox">` 手写件（#146 收敛为 §13 登记的 checkbox 基件）。原则：**改动到该页面时顺手替换，不单独开重构 issue**。
