# 实施计划：#209/#216/#217/#215/#214 平台校验与选择框可达性系列（PR #213 遗留项收口）

> 目标：按设计评审结论收口 PR #213（#177 平台选择框搜索）评审遗留的五个 issue——
> ① #209 调仓交易 `platform_code` 必填（唯一的数据完整性 bug）；
> ② #216 share-change-events 页平台必填前端校验（R1 纪律最后一块拼图）；
> ③ #217 平台选择 E2E 选择器去耦合 + 3 处接入点冒烟（升格为 #215 的前置回归网）；
> ④ #215 可搜索下拉键盘导航（combobox 模式，五者中实现风险最高）；
> ⑤ #214 平台列表加载失败显式提示（最低优先级，删悬空筛选子项）。
>
> **排期（评审已定，串行）**：**#209 → #216 → #217 → #215 → #214**。每个 issue 独立
> `feature/<issue号>-<简述>` 分支（从最新 `origin/main` 拉出）+ 独立 PR（描述含 `fixes #N`），
> squash 合入后再开下一个。
>
> **串行的硬理由（共享文件冲突）**：
> - `frontend/src/components/shared/SearchablePlatformSelect.tsx` 被 **#217**（加 testid/data-code）、
>   **#215**（选项行重写为 role=option + active 高亮态）、**#214**（选项列表 JSX 区域加
>   loading/error 分支）三方触碰；
> - `frontend/e2e/platform-select-search.spec.ts` 被 **#209**（新增调仓表单空平台拦截用例）、
>   **#216**（新增事件表单空平台拦截用例）、**#217**（定位器全面重写 + 3 处冒烟）、
>   **#215**（新增键盘流用例）四方触碰。
> 并行分支必然 rebase 冲突链，串行零冲突；且 #217 的 testid 地基必须先于 #215 的组件重写落地，
> 否则重写无回归网。
>
> **前置状态（已核实，行号以 main 当前代码 98272af 为准，实施时以结构定位为准）**：
> - `backend/app/services/trade_service.py`：`create_trade`（~L594 起）全程无基金腿平台校验；
>   仅 `cash_platform_code` 有存在性校验（~L669-673，`PLATFORM_NOT_FOUND`）。现金闸门旁路：
>   `validate_buy_cash_with_addback` 在 `check_platform is None` 时退化为全组合聚合（~L89-105）。
>   `confirm_single_trade`（~L442 起）同样无平台校验。
> - `backend/app/schemas/trade.py`：`TradeBase.platform_code: Optional[str] = None`（L10），
>   `TradeCreate`/`TradeResponse` 均继承 `TradeBase`；`TradeUpdate`（L40-53）无 platform 字段。
> - 错误码先例：`share_change_event_service.py:224-230` 已有 `PLATFORM_REQUIRED`（BusinessError，
>   默认 422）+ `PLATFORM_NOT_FOUND`（NotFoundError，404）成对用法；`subscription_service.py:368`、
>   `position_service.py:732` 有 `PLATFORM_NOT_FOUND`。
> - `trade.platform_code` 有 `ForeignKey("platform.code")`（`models/trade.py:10`）——传不存在的平台
>   今天会以 IntegrityError 爆 500，#209 的 `PLATFORM_NOT_FOUND` 校验顺带修复此潜在 500。
> - `portfolio_position` 唯一约束 `uix_position_snapshot` 含 `platform_code`
>   （`models/portfolio_position.py:32`），MySQL 中 NULL 不参与唯一比较。
> - 前端：`TradesContent.handleSubmit`（L231-246）无任何平台校验，`platform_code || undefined`
>   直接放行；申赎 R1 先例在 `SubscriptionsContent.tsx:236-240`（手动 toast 拦截）。
> - `share-change-events/page.tsx`：`handleSubmit`（L160-172）仅校验 `product_code`；
>   `PLATFORM_LEVEL_TYPES` 常量定义于 L62，显隐谓词 `PLATFORM_LEVEL_TYPES.includes(...)` 在 L237。
> - `platform-select-search.spec.ts`：`span.min-w-0` 定位 6+ 处（L80/100/161/186/219/272/339），
>   `button:has(.lucide-refresh-cw)`（L301）；已覆盖调仓筛选/调仓表单/申赎表单/现金转移/移动端两点，
>   未覆盖申赎筛选栏、share-change-events、PC positions「更新非净值资产」。
> - `usePlatformList`（`src/hooks/usePlatform.ts:10-16`）返回完整 react-query 结果（含
>   `isLoading/isError`），调用方均只解构 `data`；positions 桌面（L87）/positions 移动（L45）/
>   share-change-events（L106）为内联 `useQuery`。
> - API client 响应拦截器（`src/lib/api/client.ts:44-53`）对 401 统一 logout + 跳登录——
>   「token 失效导致空下拉」场景不存在（见 §7 风险 3）。
> - 平台删除有引用保护（「该平台已被使用，无法删除」），筛选值悬空近乎不可达（见 D4）。
> - 测试爆炸半径已核实：REST 集成测试 payload 均带 `platform_code`；单测走 factory
>   （`tests/factories.py:242` `create_trade` 默认 `platform_code="MYCF"` 且直写模型、
>   绕过 service 校验）——service 层收紧对现有测试近乎零冲击。
> - 质量门禁：后端 SQLite pytest + MySQL 方言全绿；前端无单测框架，强制 `npm run lint` +
>   `npm run build` 0 error；E2E Playwright（chromium + mobile 双 project），无数据优雅 skip 惯例。

---

## 0. 已确认决策（评审结论为基准，不重新讨论）

1. **#209 采方案 A**：service 层（`create_trade`）统一校验 `platform_code` 必填 + 存在性，
   抛 `PLATFORM_REQUIRED` / `PLATFORM_NOT_FOUND`；schema 保持 Optional 不动（错误码契约统一、
   CLI hints 可消费）；前端补 R1 式手动 toast 校验（**非**原生 `required`——平台控件已是
   自定义 Popover，issue 验收断言第 3 条机制描述以本计划为准）；CLI required 元组补
   `platform_code`。
2. **#216 原样实施**：复刻 R1，handleSubmit 增 platform_code 校验，谓词与字段显隐同源
   （`PLATFORM_LEVEL_TYPES.includes(formData.event_type)`）。
3. **#217 升格为 #215 前置回归网**：testid + `data-code` 属性（D6 推荐采纳），spec 定位器
   去 Tailwind/lucide 耦合，补 3 处接入点冒烟。
4. **#215 采方案 A（手写 listbox，零依赖）**，焦点模式定为 **combobox + aria-activedescendant**
   （焦点始终在搜索 Input，方向键移动虚拟高亮），不做 roving focus。
5. **#214 采方案 A**（组件加 `isLoading`/`isError` props + 10 处透传），最低优先级；
   **删掉悬空筛选值子项**（D4 推荐）。

### 决策表 D1~D6（需用户拍板；附推荐默认）

| # | 决策项 | 推荐默认 | 理由 |
| --- | --- | --- | --- |
| D1 | #209 是否在 `confirm_single_trade` 加 NULL 平台防御 | **绑定 D2 审计结果：审计为零 → 不加；非零 → 必加** | 防御只覆盖「存量 NULL 平台 pending 单被确认」这一条路径；存量为零时它是死代码（service 创建侧收紧后无新来源），存量非零时它是快照污染的最后闸门 |
| D2 | #209 实施前先做存量数据审计 | **做，作为 #209 的 T0 前置任务** | 个人单实例工具审计成本极低（两条 COUNT SQL）；结果同时决定 D1 与「存量修复 + NOT NULL 迁移」是否从「可选增强」变成独立工单 |
| D3 | #214 全量方案 A 还是 20% 版（`usePlatformList` onError 全局 toast） | **全量方案 A，排最后** | toast 版只解决「静默」，解决不了下拉内误导性空态与提交时「请选择平台」的归因错误；但若排期紧张，toast 版是可接受的降级（已在评审记录） |
| D4 | #214 悬空筛选值子项是否砍掉 | **砍掉（YAGNI）** | 平台删除有引用保护，筛选值悬空需「另一标签页删除零引用平台」级别的边角场景；触发按钮对失效 value 已有 raw code 兜底回显，可推断、可自愈 |
| D5 | #215 两组件焦点不对称（`SearchableProductSelect` 无显式 `autoFocus`）如何处理 | **实施时先验证 Radix Popover 默认首焦点行为；焦点不在搜索框则补 `autoFocus`，验收以「焦点在搜索框」断言为准** | `SearchablePlatformSelect` 已显式 `autoFocus`（L109），Product 版（L107-112）没有；Radix 默认聚焦弹层内首个可聚焦元素，大概率已落在 Input 上，但未经验证，先测后补 |
| D6 | #217 是否采纳 `data-code` 属性增强 | **采纳** | 现 spec 从「名称 (CODE)」文本正则解析 code（`optionCode`/`optionName`），是对文案格式的耦合，testid 迁移救不了它；选项行加 `data-code={p.code}` 后文本解析链路整体退役，成本近乎零 |

### §0.1 本轮执行决策（2026-08-22 用户拍板，覆盖上文默认）

| 决策项 | 用户拍板 | 实施影响 |
| --- | --- | --- |
| D2 存量审计 | ✅ 已执行，**零存量** | #209 的 T0 审计通过；**D1 取「不加 confirm 防御」**；「存量修复 + NOT NULL 迁移」增强项关闭（回复 issue 记录审计结果） |
| D1 confirm 防御 | **不加**（由审计为零驱动） | #209 不触碰 `confirm_single_trade` |
| D3 #214 | **20% 版**（`usePlatformList` onError 全局 toast） | #214 只改 `usePlatform.ts` hook，**不再改共享组件/10 处调用点**，与本系列其它 issue 的文件冲突消失 |
| D4 #214 悬空子项 | **砍掉** | #214 范围收窄，无 spec 改动 |
| D5 #215 焦点 | #215 **本轮暂缓** | 从排期表移除；combobox 细则 / E2E 键盘流 / D5 全部顺延，留待后续单独 issue |
| D6 #217 data-code | **采纳** | #217 保留 testid + `data-code` 增强 |

**实施顺序（更新）**：#209 → #216 → #217 → #214。
**流程分工（2026-08-22 起）**：Claude Code 负责写业务代码 + 测试用例；Hermes Agent 负责运行测试、反馈结果、提交 PR、发布 issue 评论（Claude 不 push / 不建 PR / 不发 issue 评论）。

---

## 1. 串行排期总表

| 序 | issue | 分支 | 改动面 | 风险 |
| --- | --- | --- | --- | --- |
| 1 | #209 | `feature/209-trade-platform-required` | 后端 service + 集成测试 + TradesContent + ir-cli + CLI_MANUAL + spec 新增 1 用例 | 低（测试爆炸半径已核实近零） |
| 2 | #216 | `feature/216-event-platform-check` | share-change-events 页 5 行 + spec 新增 1 用例 | 极低 |
| 3 | #217 | `feature/217-e2e-platform-testid` | SearchablePlatformSelect（testid）+ m/positions（testid）+ spec 定位器重写 + 3 处冒烟 | 低（纯测试基建 + 属性注解） |
| 4 | #215 | `feature/215-select-keyboard-a11y` | 两共享组件键盘化重写 + spec 键盘流用例 | **高（五者最高，见 §7 风险 1）** |
| 5 | #214 | `feature/214-platform-select-error-state` | SearchablePlatformSelect（状态 props）+ 10 处调用点透传 + spec 错误态用例 | 低（机械透传） |

每个 PR 合并、CI 全绿后再拉下一个分支。#209/#216 的 spec 新用例使用当时的旧定位器写法，
由 #217 统一迁移（计划中已标注，避免误以为漏改）。

---

## 2. issue #209：调仓交易 platform_code 必填

### 2.0 T0 前置任务（D2）：存量数据审计（生产库，只读）

```sql
SELECT COUNT(*) FROM trade WHERE platform_code IS NULL;
SELECT COUNT(*) FROM portfolio_position WHERE platform_code IS NULL;
```

- 均为零 → D1 取「不加 confirm 防御」；issue 中「存量修复 + NOT NULL 迁移」增强项关闭（回复 issue 记录审计结果）。
- 任一非零 → **停下**，先提存量修复 issue（pending 单删除重录或 SQL 修复；confirmed 且已入快照的单需
  unconfirm → 修复 → 重算快照，路径不同需单独设计），D1 取「必加 confirm 防御」。

### 2.1 任务拆分（有序）

**T1 后端 service 校验** — `backend/app/services/trade_service.py` `create_trade`（~L636，
product 存在性校验之后、`cash_platform_code` 规范化（~L667）之前）插入：

```python
# 平台必填 + 存在性（与 share_change_event_service PLATFORM_REQUIRED 先例同口径）：
# 基金腿平台决定持仓平台归属，缺省时现金闸门退化为全组合聚合（§2.2 旁路），必须拦截
if not platform_code:
    raise BusinessError("PLATFORM_REQUIRED", "调仓交易必须指定交易平台 platform_code")
if not db.query(Platform).filter(Platform.code == platform_code).first():
    raise NotFoundError("PLATFORM_NOT_FOUND", f"平台 {platform_code} 不存在")
```

- `Platform` 已在该文件 import（L20）。buy/sell 两方向共用此一处校验（sell 的 CASH buy 腿
  平台同样继承自基金腿）。
- **schema 不动**（`TradeCreate.platform_code` 保持 Optional；`TradeResponse` 不受影响）；
  `TradeUpdate` 不动（评审结论：pending 误单删除重建即可，不开放平台编辑——编辑需处理 CASH 腿
  平台镜像，收益不抵）。
- （D1 触发时才做）`confirm_single_trade` 在可用量校验前加 NULL 平台拒绝，同错误码。

**T2 后端集成测试** — `backend/tests/integration/test_trades.py` 新增测试类
`TestPlatformRequired`（fixture 复刻 `TestBuyTrade` 模式：`create_portfolio/create_product/
create_platform/ensure_trading_day` + confirmed CASH buy 供现金）：

1. `test_create_without_platform_rejected`：POST /api/trades 不传 `platform_code`（buy）→
   422，`detail.error == "PLATFORM_REQUIRED"`；断言 DB 中该组合无任何 trade 落库（含配对 CASH 腿，
   `test_db.query(Trade).filter_by(portfolio_code=...).count() == 0`）。
2. `test_create_sell_without_platform_rejected`：sell 方向同断言（覆盖 CASH buy 腿平台继承路径）。
3. `test_create_with_unknown_platform_rejected`：传不存在平台 → 404，`PLATFORM_NOT_FOUND`。
4. 回归：现有 71 个测试全绿（已核实无 payload 缺平台，预期零改动）。

**T3 前端表单校验** — `frontend/src/components/shared/TradesContent.tsx` `handleSubmit`
（L231-246，payload 构造前）复刻 R1：

```tsx
if (!formData.platform_code) {
  // 原生 select 替换为自定义组件后浏览器校验失效，须手动拦截（与 SubscriptionsContent 同口径）
  addToast({ type: "error", title: "表单校验失败", message: "请选择平台" });
  return;
}
```

- `cash_platform_code` **不校验**（特殊项「同交易平台」= null 是合法默认，spec 用例 8 守护）。
- 编辑 Dialog 不涉及（平台不可编辑，L819 已有说明文案）。

**T4 CLI 收紧** — `ir-cli/ir_cli/commands/trades.py`：
- `create` 的 `required` 元组（L83）改为 `("portfolio_code", "product_code", "trade_type", "trade_date", "platform_code")`；
- `--platform-code` help（L61）改为 `"平台代码(必填)"`。

**T5 CLI hints** — `ir-cli/ir_cli/hints.py` `ERROR_HINTS` 补两条（#209 否决 schema 方案的理由
就是 hints 可消费，落地须补齐闭环；现有 share-events 的 `PLATFORM_REQUIRED` 也一并受益）：

```python
"PLATFORM_REQUIRED": "该平台操作必须指定平台: 加 --platform-code <平台代码>，用 ir platform list 查询可用平台",
"PLATFORM_NOT_FOUND": "平台不存在: 用 ir platform list 查询可用平台代码",
```

**T6 文档** — `ir-cli/CLI_MANUAL.md` `ir trade create` 段（L588-616）：用法行（L594-601）
`[--platform-code <平台>]` 去方括号；参数表 L615 `--platform-code` 行「否」→「是」。
AGENTS.md 无需更新（PLATFORM_REQUIRED 沿用既有先例，无新设计决策）。

**T7 E2E** — `frontend/e2e/platform-select-search.spec.ts` 新增用例（镜像用例 3 申赎拦截形态，
放用例 3 之后）：打开「提交交易」Dialog → 选产品、填金额、**不选平台** → 提交 → 断言 toast
「表单校验失败 / 请选择平台」+ Dialog 保持打开 + 无 POST /api/trades 请求发出。
（用例 8 已验证选平台后的提交路径，不受影响。）

### 2.2 验收自查清单（映射 issue #209 断言，机制修正处已标注）

- [ ] POST /api/trades（buy/sell）不传 `platform_code` → 422，`detail.error == "PLATFORM_REQUIRED"`，无 trade/配对 CASH 腿落库 → **T2 用例 1/2**
- [ ] POST /api/trades 传不存在平台 → `PLATFORM_NOT_FOUND` → **T2 用例 3**
- [ ] 前端「提交交易」不选平台提交 → **手动校验 toast 拦截、不发起请求**（机制修正：非浏览器原生 `required`，与申赎 R1 实际行为一致）→ **T3 + T7**
- [ ] `ir trade create` 不带 `--platform-code` → CLI 报必填参数缺失 → **T4**，手动验证一次
- [ ] 有效平台创建/确认/快照回归：现有 trades/snapshot 集成测试全绿 → **T2 第 4 条 + CI**
- [ ] 新增回归测试（REST 层断言错误码）→ **T2**
- [ ] T0 审计结论已记录到 issue（含 D1 取舍）→ **T0**

---

## 3. issue #216：share-change-events 平台必填前端校验

### 3.1 任务拆分

**T1** — `frontend/src/app/portfolio/[code]/share-change-events/page.tsx` `handleSubmit`
（L160-172，`product_code` 校验之后、`submitCreate` 之前）：

```tsx
if (PLATFORM_LEVEL_TYPES.includes(formData.event_type) && !formData.platform_code) {
  // 与申赎 R1 同口径：自定义平台控件无原生 required，须手动拦截
  addToast({ type: "error", title: "表单校验失败", message: "请选择平台" });
  return;
}
```

- 谓词复用 L62 的 `PLATFORM_LEVEL_TYPES`（与 L237 字段显隐谓词同源，未来加事件类型不错位）；
  基金级事件平台字段隐藏，天然不受校验影响。

**T2 E2E** — `frontend/e2e/platform-select-search.spec.ts` 新增用例（镜像用例 3）：进入
share-change-events 页 → 新建事件 → 事件类型选「现金分红」（平台级）→ 填产品代码、**不选平台** →
提交 → 断言 toast「表单校验失败 / 请选择平台」+ Dialog 保持打开 + 无 POST 请求。
（使用当时的旧定位器写法；#217 统一迁移。该页无组合数据时按惯例优雅 skip。）

### 3.2 验收自查清单（映射 issue #216 断言）

- [ ] 平台级事件不选平台提交 → toast 拦截、Dialog 保持打开、无 POST → **T1 + T2**
- [ ] 选平台后提交行为不变 → 现有流程手动冒烟 + CI 回归
- [ ] 基金级事件（份额拆分等）提交流程不受影响 → T1 谓词仅平台级分支；手动冒烟一次

---

## 4. issue #217：E2E 选择器去耦合 + 3 处接入点冒烟

### 4.1 任务拆分

**T1 组件注解** — `frontend/src/components/shared/SearchablePlatformSelect.tsx`：
- 触发按钮（L91-104）加 `data-testid="platform-trigger"`；
- 平台选项行（L137-157）加 `data-testid="platform-option"` + `data-code={p.code}`（D6）；
- 特殊项行（L118-129）加 `data-testid="platform-special-option"`；
- 空态 `<p>`（L132）加 `data-testid="platform-empty"`。
- 同页多实例由测试用 scope（Dialog/页面区域 locator）限定，不追求全局唯一。

**T2 移动端触发器解耦** — `frontend/src/app/m/portfolio/[code]/positions/page.tsx`：「更新非净值
资产」的纯图标按钮（spec L301 `button:has(.lucide-refresh-cw)` 的目标）加
`data-testid="cash-update-trigger"`。

**T3 spec 定位器重写** — `frontend/e2e/platform-select-search.spec.ts`：
- `platformOptionTexts`/`firstPlatformOption`/`expectFilteredOptions` 等 helper 改用
  `[data-testid="platform-option"]`；code 改从 `data-code` 属性读取，**删除 `optionCode`/
  `optionName` 文本解析**（触发按钮回显文本断言保留——那是用户可见契约，不是实现耦合）；
- `platformTrigger`（L132-134）改 `[data-testid="platform-trigger"]` + hasText；
- 用例 4 的 `div[aria-disabled="true"]`（L282）改 testid + 属性过滤；
- L301 改 `[data-testid="cash-update-trigger"]`；
- #209/#216 新增的两个 toast 拦截用例一并迁移到新定位器。
- 迁移后 grep 验证：`span.min-w-0`、`lucide` 在 spec 中零残留。

**T4 三处接入点冒烟**（每处最小步骤：打开弹层 → 搜索 → 点选 → 回显断言；无数据优雅 skip）：
1. **申赎筛选栏**（`SubscriptionsContent.tsx:365`，特殊项「全部平台」）：进申赎页 → 打开筛选
   平台弹层 → 搜索 → 点选 → 触发按钮回显 name (code)；可顺带断言列表请求带 `platform_code`
   （镜像 spec 用例 1 的请求断言形态）。
2. **share-change-events**（`page.tsx:240`，条件渲染——先在建事件 Dialog 中选平台级事件类型
   使平台框出现，再走完搜索点选流）。三处中接线风险最高，放第一个写。
3. **PC positions「更新非净值资产」**（`positions/page.tsx:347`）：桌面项目下开 Dialog →
   搜索点选 → 回显（移动端同控件已由用例 5 覆盖，桌面端补缺口）。

**T5 验证实验**：临时移除选项 span 的 `min-w-0` 类 → 全量平台选择 E2E 仍全绿 → 恢复。
（验收断言 2 的以实验证伪耦合写法，保留。）

### 4.2 验收自查清单（映射 issue #217 断言）

- [ ] spec 不再依赖 Tailwind 工具类名/lucide 类名（grep 验证）→ **T3**
- [ ] 移除/改名 `min-w-0` 后 E2E 仍全绿 → **T5**
- [ ] 3 处新冒烟在 chromium 项目通过、遵循无数据优雅 skip → **T4**
- [ ] （D6 增强）code 读取不依赖选项文案格式 → **T3 删除 optionCode/optionName**

---

## 5. issue #215：可搜索下拉键盘导航（combobox + aria-activedescendant）

> 五者中实现风险最高（§7 风险 1）。细则在此写死，实现者不做自由裁量。

### 5.1 交互细则（两组件一致）

- **焦点模式**：焦点**始终在搜索 Input**（combobox 模式），不做焦点移交到选项列表。
  - 搜索 Input：`role="combobox"` + `aria-expanded` + `aria-controls=<listbox id>` +
    `aria-activedescendant=<active 选项 id>`；
  - 选项容器：`role="listbox"` + 稳定 `id`；选项行：`role="option"` + 稳定 `id`
    （平台：`platform-option-${p.code}`；产品：`product-option-${code}-${market}`）+
    `aria-selected`；禁用项保留 `aria-disabled="true"` 且**不参与** active 序列。
- **active 索引状态机**（`activeIndex`，指向过滤后含特殊项的完整序列）：
  - 打开弹层 / 过滤词变化 → 重置到**首个非禁用项**（无任何可选项则 -1）；
  - ↓/↑ 移动，**clamp 不 wrap**（与原生 select 一致）；Home/End 跳首/尾非禁用项（成本低，保留）；
  - Enter → 选中 active 项；**无 active（-1）时取首个非禁用项**（过滤到只剩一项不应还要先按 ↓）；
  - **鼠标 hover 同步 `activeIndex`**（鼠标键盘高亮同源，杜绝双高亮打架）；active 项与 hover 项
    共用 `bg-muted` 高亮样式；
  - 特殊项（全部平台/同交易平台）参与 active 序列（评审已确认）；点选语义不变（回传 null）；
  - Esc 关闭弹层 + 重置搜索词——Radix 默认行为 + 现有 `onOpenChange` 已覆盖，降级为回归断言。
- **keydown 挂在搜索 Input 上**（焦点不离开，输入不中断）。

### 5.2 任务拆分

**T1** — `frontend/src/components/shared/SearchablePlatformSelect.tsx`：按 §5.1 改造
（activeIndex 状态 + keydown + role/aria 注解 + hover 同步）。保留 #217 的
`data-testid`/`data-code` 不动（E2E 地基不破坏）。

**T2** — `frontend/src/components/shared/SearchableProductSelect.tsx`：同构改造。
差异点：无特殊项、有服务端防抖过滤（activeIndex 在 `items` 变化时同样重置到首项）、
无禁用项。**D5**：先验证 Radix 默认焦点是否落在搜索 Input（L107-112 无显式 `autoFocus`），
不落则补 `autoFocus`，与平台版对齐。

**T3 lint/build 门禁**：`npm run lint` + `npm run build` 0 error。

**T4 E2E 键盘流用例** — `frontend/e2e/platform-select-search.spec.ts` 新增（定位全部走 #217 的
testid/`data-code`）：
1. 平台选择框（调仓表单内）：Tab 到触发按钮 → Enter 打开 → **断言焦点在搜索框** → 输入过滤词 →
   ↓/↑ 移动（断言高亮项 `aria-selected`/样式变化，跳过禁用项场景用现金转移互斥项覆盖）→
   Enter 选中 → 弹层关闭、触发按钮回显 name (code) → 重开 → Esc 关闭、搜索词已重置。
2. 特殊项参与序列：过滤词为空时 ↓ 从「全部平台/同交易平台」开始移动。
3. 产品选择框（提交交易表单）：同主流（打开→焦点断言→过滤→↓→Enter→回显）。

### 5.3 验收自查清单（映射 issue #215 断言）

- [ ] Tab 到触发按钮 → Enter 打开、焦点在搜索框 → **T4-1**（产品框经 **T4-3**，含 D5 处理）
- [ ] 过滤后 ↓/↑ 高亮移动，特殊项参与序列、禁用项被跳过 → **T4-1/T4-2**
- [ ] Enter 选中当前高亮项、弹层关闭、值回传（回显 name (code)）→ **T4-1**
- [ ] Esc 关闭、搜索词重置 → **T4-1**（回归断言）
- [ ] 产品选择框键盘流同上 → **T4-3**
- [ ] #217 既有 E2E 全绿（组件重写未破坏 testid 地基）→ **CI**

---

## 6. issue #214：平台列表加载失败显式提示（最低优先级）

> 范围已按 D4 砍掉「悬空筛选值」子项；issue 验收断言第 4 条随之删除。

### 6.1 任务拆分

**T1 组件状态分支** — `frontend/src/components/shared/SearchablePlatformSelect.tsx`：
- 新增 props：`isLoading?: boolean`、`isError?: boolean`（默认 false，调用方未透传时行为与现状
  一致，向后兼容）；
- `isError`：触发按钮 `disabled` + 弹层内（或按钮旁）渲染「平台列表加载失败，请稍后重试」
  （接口恢复 → query 重试成功 → isError 翻 false → 自动恢复可用，无需手动刷新）；
- `isLoading`：弹层内渲染加载文案/spinner（Loader2，与 Product 版 L115-118 形态一致），
  **不显示**「无符合条件的平台」；
- 三分支优先级：isError > isLoading > 现有空态（「无符合条件的平台」仅余纯搜索无匹配场景）。
- 落在 #215 重写后的选项列表 JSX 区域上，一次性写对，不回改。

**T2 十处调用点透传**（机械改动，每处解构补 `isLoading`/`isError` 并逐 prop 传入）：
- `frontend/src/components/shared/TradesContent.tsx`（L152 `usePlatformList`；3 处组件实例：
  筛选栏 L358、表单交易平台 L636、现金平台 L648）；
- `frontend/src/components/shared/SubscriptionsContent.tsx`（L148；2 处：L365、L475）；
- `frontend/src/app/portfolio/[code]/positions/page.tsx`（L87 内联 useQuery；3 处：L347、L430、L440）；
- `frontend/src/app/m/portfolio/[code]/positions/page.tsx`（L45 内联 useQuery；1 处：L201）；
- `frontend/src/app/portfolio/[code]/share-change-events/page.tsx`（L106 内联 useQuery；1 处：L240）。
- 内联 `useQuery` 与 `usePlatformList` 并存不动（不顺手重构，最小 diff）。

**T3 E2E 错误态用例** — `frontend/e2e/platform-select-search.spec.ts` 新增：`page.route` 拦截
`/api/platforms` 返回 500 → 进调仓页 → 筛选平台触发按钮 disabled / 打开表单平台框显示
「平台列表加载失败」→ 断言**不出现**「无符合条件的平台」；解除拦截重开 → 正常显示列表。

### 6.2 验收自查清单（映射 issue #214 断言，已按 D4 删第 4 条）

- [ ] 平台接口 5xx → 打开任一平台选择框 → 「平台列表加载失败」而非「无符合条件的平台」→ **T3**
- [ ] 接口恢复后重开 → 正常显示平台列表 → **T3**（route 解除拦截分支）
- [ ] 接口失败期间提交依赖平台的表单 → 前端拦截（触发 disabled + #209/#216 的 toast 校验兜底），
  不出现误导性「请选择平台」→ **T1 + T3 断言 disabled**
- [ ] ~~悬空筛选值重置~~ → **D4 已砍，不做**

---

## 7. 风险与备注

1. **#215 是五者中实现风险最高的改动**：active 索引状态机（过滤/特殊项/禁用项/hover 四路输入
   收敛）+ 两组件同步改造 + 焦点细节（D5）。缓解措施：#217 的 testid 回归网先行（排期已保证）；
   §5.1 细则写死裁量点；T4 键盘用例逐条对应验收断言。若实现中发现 combobox 模式与 Radix Popover
   焦点管理冲突（如 Popover 关闭时焦点返还触发按钮的行为），在 PR 中记录取舍，不静默绕过。
2. **#209 收紧的测试爆炸半径近零**（已核实）：REST 集成测试 payload 均带平台；factory 直写模型
   绕过 service 校验。但 **CLI required 元组变化影响脚本化调用**——`ir trade create` 旧脚本缺
   `--platform-code` 将从「静默创建无平台交易」变为「显式报必填缺失」，这正是目的；CLI_MANUAL
   同步（T6），hints 兜底（T5）。
3. **#214 issue 正文的触发场景描述有事实错误（评审已确认，实施时以本节为准）**：「token 失效」
   不构成空下拉场景——`client.ts:44-53` 对 401 统一 logout + 跳登录。真实触发面仅后端 5xx /
   网络失败 / 30s 超时（react-query 默认重试 3 次，瞬时故障多能自愈）。这不推翻方案 A，但是
   它排最低优先级的依据；实施 PR 描述中应如实修正，避免后续误判 urgency。
4. **#209 的 FK 附带修复**：`trade.platform_code` 有外键（`models/trade.py:10`），今天传不存在
   的平台会 IntegrityError 爆 500；`PLATFORM_NOT_FOUND` 校验顺带修复。PR 描述中记一笔。
5. **NOT NULL 迁移**（`trade.platform_code` / `portfolio_position.platform_code`）明确留在本系列
   之外：依赖 T0 审计结果，若做需独立 issue + Alembic 迁移（注意 §4.5 可逆性验证/豁免流程）。
6. **spec 文件四方串行触碰**（#209 → #216 → #217 → #215/214）：#209/#216 新用例用旧定位器写、
   #217 统一迁移是刻意安排（让 #217 的迁移覆盖全部既有用例，迁移质量由全绿背书），不是漏改。
7. 各 PR 描述按 §8.3 模板：改动内容 / `fixes #N` / 测试验证 / 部署影响（本系列全部无 DB 迁移、
   无新依赖——#215 方案 A 零依赖是评审确认的硬约束）。

---

## 8. 附：本计划与评审结论的偏差

无。方案选择（#209 A、#216 原样、#217 升格 + data-code、#215 A + combobox 细则、#214 A 删子项）、
排期（#209 → #216 → #217 → #215 → #214）、开放点处置（D1~D6 按推荐默认）均直接采用评审结论；
D1/D2 以 T0 审计为执行闸门，其余无待议项。
