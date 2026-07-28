# 交易管理API

<cite>
**本文引用的文件**
- [backend/app/main.py](file://backend/app/main.py)
- [backend/app/routers/trades.py](file://backend/app/routers/trades.py)
- [backend/app/schemas/trade.py](file://backend/app/schemas/trade.py)
- [backend/app/models/trade.py](file://backend/app/models/trade.py)
- [backend/app/models/portfolio.py](file://backend/app/models/portfolio.py)
- [backend/app/models/product.py](file://backend/app/models/product.py)
- [backend/app/models/portfolio_position.py](file://backend/app/models/portfolio_position.py)
- [backend/app/models/subscription.py](file://backend/app/models/subscription.py)
- [backend/app/models/price_record.py](file://backend/app/models/price_record.py)
- [backend/app/services/trading_calendar_service.py](file://backend/app/services/trading_calendar_service.py)
- [backend/app/dependencies.py](file://backend/app/dependencies.py)
- [frontend/src/app/portfolio/[code]/trades/page.tsx](file://frontend/src/app/portfolio/[code]/trades/page.tsx)
- [frontend/src/components/shared/TradeForm.tsx](file://frontend/src/components/shared/TradeForm.tsx)
- [frontend/src/hooks/useTrade.ts](file://frontend/src/hooks/useTrade.ts)
- [frontend/src/types/trade.ts](file://frontend/src/types/trade.ts)
</cite>

## 更新摘要
**变更内容**
- 新增交易预览功能，提供GET /api/trades/{id}/preview接口
- 增强交易服务中的calculate_confirm_preview函数
- 改进交易Schema，添加预览响应模型
- 交易预览系统允许用户在执行前验证交易而不持久化数据

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构概览](#架构概览)
5. [详细组件分析](#详细组件分析)
6. [依赖分析](#依赖分析)
7. [性能考虑](#性能考虑)
8. [故障排除指南](#故障排除指南)
9. [结论](#结论)
10. [附录](#附录)

## 简介
本文件为 InvestRing 交易管理模块的完整API文档，覆盖交易CRUD操作、交易执行与确认、状态管理、费用计算、查询接口及权限控制。文档面向前后端开发者与运维人员，提供HTTP方法、URL模式、请求/响应格式、权限要求、示例与约束说明，帮助快速集成与排错。

**重要更新** 系统新增了交易预览功能，允许用户在正式执行交易前进行验证和模拟，确保交易参数的正确性而不产生实际的数据变更。同时增强了现金交易处理机制，现在禁止直接创建裸CASH交易，只允许通过受控路径创建，确保资金流动的完整性和可追溯性。

## 项目结构
交易管理API位于后端FastAPI应用中，通过统一入口注册到根路径下。前端通过React组件与Hooks调用后端接口，实现交易的创建、查询、确认、取消与预览。

```mermaid
graph TB
subgraph "后端"
A["FastAPI 应用<br/>app/main.py"]
B["交易路由<br/>routers/trades.py"]
C["交易模型<br/>models/trade.py"]
D["交易Schema<br/>schemas/trade.py"]
E["交易日历服务<br/>services/trading_calendar_service.py"]
F["权限依赖<br/>dependencies.py"]
G["现金转账服务<br/>cash_transfers.py"]
H["交易预览功能<br/>calculate_confirm_preview"]
end
subgraph "前端"
I["交易页面<br/>frontend/src/app/portfolio/[code]/trades/page.tsx"]
J["交易表单<br/>frontend/src/components/shared/TradeForm.tsx"]
K["交易Hooks<br/>frontend/src/hooks/useTrade.ts"]
L["类型定义<br/>frontend/src/types/trade.ts"]
M["交易预览组件<br/>TradePreview"]
end
A --> B
B --> C
B --> D
B --> E
B --> F
B --> G
B --> H
I --> J
I --> K
J --> K
K --> L
K --> M
```

**图表来源**
- [backend/app/main.py:32-48](file://backend/app/main.py#L32-L48)
- [backend/app/routers/trades.py:108](file://backend/app/routers/trades.py#L108)
- [backend/app/services/trading_calendar_service.py:15](file://backend/app/services/trading_calendar_service.py#L15)

**章节来源**
- [backend/app/main.py:32-48](file://backend/app/main.py#L32-L48)

## 核心组件
- 路由器：交易路由集中于 [routers/trades.py](file://backend/app/routers/trades.py)，提供交易CRUD、确认、取消、预览与查询。
- 模型：交易实体定义于 [models/trade.py](file://backend/app/models/trade.py)，包含字段、索引与外键约束。
- Schema：请求/响应数据结构定义于 [schemas/trade.py](file://backend/app/schemas/trade.py)，用于Pydantic校验与序列化，包含新的预览响应模型。
- 权限：用户与管理员权限校验位于 [dependencies.py](file://backend/app/dependencies.py)。
- 交易日历：交易日判断与同步逻辑位于 [services/trading_calendar_service.py](file://backend/app/services/trading_calendar_service.py)。
- 现金转账：跨平台现金转移处理位于 [cash_transfers.py](file://backend/app/routers/cash_transfers.py)。
- 交易预览：新增的交易预览功能提供execute前的验证能力。
- 前端：交易页面、表单与Hooks位于 [frontend](file://frontend/src/) 目录，负责调用后端API并展示结果，包括预览功能。

**章节来源**
- [backend/app/routers/trades.py:108](file://backend/app/routers/trades.py#L108)
- [backend/app/models/trade.py:5-32](file://backend/app/models/trade.py#L5-L32)
- [backend/app/schemas/trade.py:6-45](file://backend/app/schemas/trade.py#L6-L45)
- [backend/app/dependencies.py:49-146](file://backend/app/dependencies.py#L49-L146)
- [backend/app/services/trading_calendar_service.py:15-125](file://backend/app/services/trading_calendar_service.py#L15-L125)

## 架构概览
交易管理API采用分层设计：路由层处理HTTP请求与权限校验，服务层封装业务逻辑（可用资金/份额计算、净值确认、交易日校验、交易预览），数据层通过SQLAlchemy模型与数据库交互。

```mermaid
sequenceDiagram
participant FE as "前端"
participant API as "FastAPI 路由"
participant SVC as "业务逻辑"
participant DB as "数据库"
FE->>API : GET /api/trades/{id}/preview
API->>SVC : calculate_confirm_preview()
SVC->>DB : 读取交易及相关数据
SVC->>SVC : 验证交易日/组合状态/产品存在性
SVC->>DB : 计算可用现金/份额
alt CASH交易
SVC->>SVC : 验证transfer_group配对约束
alt 无配对或配对无效
SVC-->>API : 返回CASH_TRADE_FORBIDDEN错误
API-->>FE : 422 错误响应
else 配对有效
SVC->>SVC : 生成预览结果不持久化
API-->>FE : TradePreviewResponse
end
else 非CASH交易
SVC->>SVC : 生成预览结果不持久化
API-->>FE : TradePreviewResponse
end
```

**图表来源**
- [backend/app/routers/trades.py:292-402](file://backend/app/routers/trades.py#L292-L402)
- [backend/app/models/trade.py:5-32](file://backend/app/models/trade.py#L5-L32)

## 详细组件分析

### 交易路由与接口定义
- 基础路径：/api/trades
- 路由注册：见 [backend/app/main.py](file://backend/app/main.py#L42)

接口一览（按功能分组）：

- 交易列表查询
  - 方法与路径：GET /api/trades
  - 查询参数：
    - portfolio_code: 组合代码（可选）
    - page: 页码，默认1
    - page_size: 每页条数，默认20
  - 权限：普通用户（需登录）
  - 响应：分页对象，包含items、total、page、page_size
  - 实现参考：[backend/app/routers/trades.py:271-289](file://backend/app/routers/trades.py#L271-L289)

- 单个交易查询
  - 方法与路径：GET /api/trades/{id}
  - 权限：普通用户（需登录）
  - 响应：TradeResponse
  - 实现参考：[backend/app/routers/trades.py:405-414](file://backend/app/routers/trades.py#L405-L414)

- **新增** 交易预览
  - 方法与路径：GET /api/trades/{id}/preview
  - 权限：普通用户（需登录）
  - 功能：在不持久化数据的情况下验证交易参数和计算结果
  - 业务要点：
    - 验证交易日有效性
    - 检查组合状态和产品存在性
    - 计算预估金额、费用和份额
    - 验证CASH交易配对约束
    - 返回预览结果但不修改任何数据
  - 响应：TradePreviewResponse，包含预估的交易详情
  - 实现参考：[backend/app/routers/trades.py:415-416](file://backend/app/routers/trades.py#L415-L416)

- 创建交易（买入/卖出）
  - 方法与路径：POST /api/trades
  - 请求体：TradeCreate
  - 权限：管理员（admin）
  - 业务要点：
    - 交易日校验：仅允许交易日
    - 组合状态：仅允许active状态组合
    - 产品存在性：按product_code与market匹配
    - **新增** CASH交易强制配对验证：禁止直接创建裸CASH交易
    - **新增** transfer_group必填约束：所有CASH交易必须提供有效的配对组标识
    - 买入校验：amount > 0，且不超过可用现金
    - 卖出校验：shares > 0，且不超过可用份额
    - 自动计算：根据price、fee与实际金额推导amount/shares
  - 响应：TradeResponse（初始状态为pending）
  - 实现参考：[backend/app/routers/trades.py:292-402](file://backend/app/routers/trades.py#L292-L402)

- 更新交易
  - 方法与路径：PUT /api/trades/{id}
  - 请求体：TradeUpdate（支持部分字段更新）
  - 权限：管理员（admin）
  - 安全验证：**新增** 已确认交易不可直接修改，需先取消确认
  - 响应：TradeResponse
  - 实现参考：[backend/app/routers/trades.py:535-561](file://backend/app/routers/trades.py#L535-L561)

- 删除交易
  - 方法与路径：DELETE /api/trades/{id}
  - 权限：管理员（admin）
  - 安全验证：**新增** 已确认交易不可直接删除，需先取消确认
  - 响应：成功消息
  - 实现参考：[backend/app/routers/trades.py:563-585](file://backend/app/routers/trades.py#L563-L585)

- 确认交易
  - 方法与路径：POST /api/trades/{id}/confirm
  - 查询参数：
    - confirm_date: 确认日期（可选，默认根据产品确认周期推算）
    - price: 确认价格（可选，净值型产品通常不填，系统自动取净值）
  - 权限：管理员（admin）
  - 业务要点：
    - 仅pending状态可确认
    - 净值型产品（OEF/LOF CN_OTC）必须有T日净值（QDII禁止向前查找）
    - 非净值型产品若传入price，则按price重算amount/shares
    - 确认后更新confirm_date与最终amount/price/shares
  - 响应：包含message、id、portfolio_code、trade_type、status、confirm_date与trade对象
  - 实现参考：[backend/app/routers/trades.py:417-504](file://backend/app/routers/trades.py#L417-504)

- 取消交易
  - 方法与路径：POST /api/trades/{id}/cancel
  - 权限：管理员（admin）
  - 业务要点：
    - 仅pending状态可取消
    - 仅场外（CN_OTC）的pending可取消，场内（CN_EXCHANGE）不可取消
  - 响应：成功消息
  - 实现参考：[backend/app/routers/trades.py:507-532](file://backend/app/routers/trades.py#L507-532)

**新增** CASH交易受控创建路径：
系统现在只允许通过以下三种受控路径创建CASH交易：

1. **申购赎回操作**：通过订阅服务创建的申购赎回交易
2. **基金再平衡配对**：通过投资组合再平衡流程创建的配对交易
3. **跨平台现金转移**：通过现金转账服务创建的平台间资金调拨

请求/响应模式与字段说明（基于Schema与模型）：
- TradeBase/TradeCreate/TradeUpdate/TradeResponse 字段定义参见 [backend/app/schemas/trade.py:6-45](file://backend/app/schemas/trade.py#L6-L45)
- Trade模型字段与约束参见 [backend/app/models/trade.py:5-32](file://backend/app/models/trade.py#L5-L32)

权限与鉴权：
- 普通用户：通过Bearer Token鉴权，见 [backend/app/dependencies.py:49-111](file://backend/app/dependencies.py#L49-L111)
- 管理员：除登录外，还需角色为admin，见 [backend/app/dependencies.py:114-129](file://backend/app/dependencies.py#L114-L129)

交易日历与确认周期：
- 交易日判断：见 [backend/app/services/trading_calendar_service.py:110-124](file://backend/app/services/trading_calendar_service.py#L110-L124)
- 产品确认周期：Product.confirm_days决定T+N确认周期，见 [backend/app/models/product.py](file://backend/app/models/product.py#L13)

前端集成要点：
- 交易页面与表单：见 [frontend/src/app/portfolio/[code]/trades/page.tsx](file://frontend/src/app/portfolio/[code]/trades/page.tsx#L33-L44) 与 [frontend/src/components/shared/TradeForm.tsx:25-46](file://frontend/src/components/shared/TradeForm.tsx#L25-L46)
- Hooks与类型：见 [frontend/src/hooks/useTrade.ts:22-103](file://frontend/src/hooks/useTrade.ts#L22-L103) 与 [frontend/src/types/trade.ts:1-45](file://frontend/src/types/trade.ts#L1-L45)

**章节来源**
- [backend/app/routers/trades.py:271-585](file://backend/app/routers/trades.py#L271-L585)
- [backend/app/schemas/trade.py:6-45](file://backend/app/schemas/trade.py#L6-L45)
- [backend/app/models/trade.py:5-32](file://backend/app/models/trade.py#L5-L32)
- [backend/app/dependencies.py:49-129](file://backend/app/dependencies.py#L49-L129)
- [backend/app/services/trading_calendar_service.py:110-124](file://backend/app/services/trading_calendar_service.py#L110-L124)
- [backend/app/models/product.py:13](file://backend/app/models/product.py#L13)
- [frontend/src/app/portfolio/[code]/trades/page.tsx:33-44](file://frontend/src/app/portfolio/[code]/trades/page.tsx#L33-L44)
- [frontend/src/components/shared/TradeForm.tsx:25-46](file://frontend/src/components/shared/TradeForm.tsx#L25-L46)
- [frontend/src/hooks/useTrade.ts:22-103](file://frontend/src/hooks/useTrade.ts#L22-L103)
- [frontend/src/types/trade.ts:1-45](file://frontend/src/types/trade.ts#L1-L45)

### 交易预览功能详解
**新增** 交易预览功能提供了在执行交易前的验证和模拟能力，允许用户在不持久化数据的情况下查看交易的实际影响。

#### 预览接口特性
- **无副作用**：预览操作不会修改数据库中的任何数据
- **实时计算**：基于当前市场数据和账户状态进行实时计算
- **完整验证**：执行完整的业务逻辑验证，包括交易日、组合状态、产品存在性等
- **预估结果**：返回预估的金额、费用和份额等关键信息

#### 预览业务流程
```mermaid
flowchart TD
A["用户请求交易预览"] --> B["验证交易ID存在性"]
B --> C["获取交易详细信息"]
C --> D["验证交易日有效性"]
D --> E["检查组合状态"]
E --> F["验证产品存在性"]
F --> G["计算可用资金/份额"]
G --> H{"是否为CASH交易"}
H --> |是| I["验证transfer_group配对"]
H --> |否| J["跳过配对验证"]
I --> K["生成预览结果"]
J --> K
K --> L["返回TradePreviewResponse"]
```

**图表来源**
- [backend/app/routers/trades.py:415-416](file://backend/app/routers/trades.py#L415-L416)

#### 预览响应模型
TradePreviewResponse包含以下关键字段：
- trade_id: 交易ID
- portfolio_code: 组合代码
- product_code: 产品代码
- trade_type: 交易类型
- estimated_amount: 预估金额
- estimated_shares: 预估份额
- estimated_fee: 预估费用
- estimated_actual_amount: 预估实际金额
- validation_status: 验证状态
- warnings: 警告信息列表

#### 使用场景
1. **交易参数验证**：在提交交易前验证参数是否正确
2. **成本估算**：预估交易成本和费用
3. **风险检查**：检查是否存在潜在的风险或限制
4. **用户体验优化**：提供实时的交易反馈

**章节来源**
- [backend/app/routers/trades.py:415-416](file://backend/app/routers/trades.py#L415-L416)

### 交易状态管理与流程
交易状态包括：pending（待确认）、confirmed（已确认）、cancelled（已取消）。确认流程根据产品类型与市场区分净值型与非净值型，并结合交易日历与确认周期自动推导确认日期。

```mermaid
stateDiagram-v2
[*] --> 待确认
待确认 --> 已确认 : "管理员确认"
待确认 --> 已取消 : "管理员取消仅场外pending"
已确认 --> [*]
已取消 --> [*]
```

**图表来源**
- [backend/app/routers/trades.py:417-532](file://backend/app/routers/trades.py#L417-532)

**章节来源**
- [backend/app/routers/trades.py:417-532](file://backend/app/routers/trades.py#L417-L532)

### 交易费用与金额计算
- 买入：amount = actual_amount - fee；shares = amount / price
- 卖出：amount = actual_amount + fee；shares为输入
- 确认时若传入price，按price重算；净值型产品按T日净值自动计算

**章节来源**
- [backend/app/routers/trades.py:337-395](file://backend/app/routers/trades.py#L337-L395)
- [backend/app/routers/trades.py:479-489](file://backend/app/routers/trades.py#L479-L489)

### 可用资金与可用份额计算
- 可用现金（Cash）：基于最新快照现金，叠加/扣减未生成快照的确认申赎、待确认买入、已确认买入与已确认卖出
- 可用份额：基于最新快照份额，扣减待确认/已确认卖出

```mermaid
flowchart TD
Start(["开始"]) --> GetSnap["获取最新快照日期"]
GetSnap --> InitCash["初始化可用现金=CASH快照金额"]
InitCash --> AddSubs["累加未生成快照的已确认申购金额"]
AddSubs --> SubRedeems["减去未生成快照的已确认赎回金额"]
SubRedeems --> SubPendingBuys["减去所有待确认买入金额"]
SubPendingBuys --> SubConfirmedBuys["减去未生成快照的已确认买入金额"]
SubConfirmedBuys --> AddConfirmedSells["加上未生成快照的已确认卖出金额"]
AddConfirmedSells --> EndCash["得到可用现金"]
Start2(["开始"]) --> GetSnap2["获取最新快照日期"]
GetSnap2 --> InitShares["初始化可用份额=份额快照"]
InitShares --> SubPendingSells["减去所有待确认卖出份额"]
SubPendingSells --> SubConfirmedSells2["减去未生成快照的已确认卖出份额"]
SubConfirmedSells2 --> EndShares["得到可用份额"]
```

**图表来源**
- [backend/app/routers/trades.py:128-217](file://backend/app/routers/trades.py#L128-L217)
- [backend/app/routers/trades.py:220-268](file://backend/app/routers/trades.py#L220-L268)

**章节来源**
- [backend/app/routers/trades.py:128-268](file://backend/app/routers/trades.py#L128-L268)

### 净值确认与QDII规则
- 净值型产品（OEF/LOF CN_OTC）：
  - QDII：必须取T日净值，禁止向前查找；缺失时报错
  - 非QDII：取T日或最近交易日净值；缺失时返回None
- 确认时若前端传入price，则优先使用该价格；否则使用系统获取的净值

**章节来源**
- [backend/app/routers/trades.py:53-105](file://backend/app/routers/trades.py#L53-L105)
- [backend/app/models/product.py:11-14](file://backend/app/models/product.py#L11-L14)

### 安全验证与数据完整性保护
**新增** 交易管理包含严格的安全验证机制，防止对已确认交易进行直接修改或删除操作，确保数据完整性与审计追踪。

#### 已确认交易保护机制
- **修改保护**：当尝试修改状态为confirmed的交易时，系统将拒绝请求并提示先取消确认
- **删除保护**：当尝试删除状态为confirmed的交易时，系统将拒绝请求并提示先取消确认
- **错误响应**：返回标准的HTTP 422状态码和详细的错误信息

#### 安全验证实现细节
- **验证时机**：在update_trade和delete_trade操作中进行状态检查
- **错误类型**：INVALID_STATUS（状态验证失败）
- **错误消息**：提供清晰的指导信息，建议用户先执行取消确认操作

**章节来源**
- [backend/app/routers/trades.py:546-553](file://backend/app/routers/trades.py#L546-L553)
- [backend/app/routers/trades.py:573-580](file://backend/app/routers/trades.py#L573-L580)

### CASH交易强制配对验证机制
**新增** 系统现在实施了严格的CASH交易配对验证机制，确保所有现金交易都有完整的配对记录，防止资金流向的不透明性。

#### 配对验证规则
- **transfer_group必填**：所有CASH类型的交易必须提供有效的transfer_group标识符
- **配对完整性**：同一transfer_group内的交易必须成对出现，确保资金流入流出的平衡
- **时间窗口限制**：配对交易必须在合理的时间范围内创建

#### 受控创建路径
系统现在只允许通过以下三种受控路径创建CASH交易：

1. **申购赎回操作**：通过订阅服务创建的申购赎回交易
   - 自动分配transfer_group标识符
   - 与对应的产品交易形成配对关系
   
2. **基金再平衡配对**：通过投资组合再平衡流程创建的配对交易
   - 由再平衡算法自动生成配对交易
   - 确保资产配置的精确调整
   
3. **跨平台现金转移**：通过现金转账服务创建的平台间资金调拨
   - 通过专门的现金转账API创建
   - 自动建立平台间的资金流转记录

#### 错误处理
- **CASH_TRADE_FORBIDDEN**：当尝试直接创建裸CASH交易时返回此错误
- **MISSING_TRANSFER_GROUP**：当CASH交易缺少必需的transfer_group字段时返回
- **INVALID_PAIRING**：当配对交易不完整或不匹配时返回

**章节来源**
- [backend/app/routers/trades.py:292-402](file://backend/app/routers/trades.py#L292-L402)
- [backend/app/routers/cash_transfers.py](file://backend/app/routers/cash_transfers.py)

## 依赖分析
- 路由依赖：交易路由依赖数据库会话、当前用户与管理员权限
- 业务依赖：交易逻辑依赖交易日历服务、产品模型、价格记录、组合与持仓快照
- 前端依赖：交易页面通过Hooks调用API，类型与响应结构与后端保持一致

```mermaid
graph LR
R["路由 trades.py"] --> M["模型 trade.py"]
R --> S["Schema trade.py"]
R --> P["模型 product.py"]
R --> PP["模型 portfolio_position.py"]
R --> PR["模型 price_record.py"]
R --> SC["服务 trading_calendar_service.py"]
R --> D["依赖 dependencies.py"]
R --> CT["现金转账 cash_transfers.py"]
R --> TP["交易预览 calculate_confirm_preview"]
CT --> TG["transfer_group 配对验证"]
TP --> VC["验证组件"]
```

**图表来源**
- [backend/app/routers/trades.py:1-16](file://backend/app/routers/trades.py#L1-L16)
- [backend/app/models/trade.py:5-32](file://backend/app/models/trade.py#L5-L32)
- [backend/app/models/product.py:5-22](file://backend/app/models/product.py#L5-22)
- [backend/app/models/portfolio_position.py:5-34](file://backend/app/models/portfolio_position.py#L5-34)
- [backend/app/models/price_record.py:5-28](file://backend/app/models/price_record.py#L5-28)
- [backend/app/services/trading_calendar_service.py:15-125](file://backend/app/services/trading_calendar_service.py#L15-L125)
- [backend/app/dependencies.py:49-129](file://backend/app/dependencies.py#L49-129)

**章节来源**
- [backend/app/routers/trades.py:1-16](file://backend/app/routers/trades.py#L1-L16)
- [backend/app/models/trade.py:5-32](file://backend/app/models/trade.py#L5-L32)
- [backend/app/models/product.py:5-22](file://backend/app/models/product.py#L5-22)
- [backend/app/models/portfolio_position.py:5-34](file://backend/app/models/portfolio_position.py#L5-34)
- [backend/app/models/price_record.py:5-28](file://backend/app/models/price_record.py#L5-28)
- [backend/app/services/trading_calendar_service.py:15-125](file://backend/app/services/trading_calendar_service.py#L15-L125)
- [backend/app/dependencies.py:49-129](file://backend/app/dependencies.py#L49-129)

## 性能考虑
- 分页查询：列表接口默认每页20条，避免一次性加载过多数据
- 交易日历批量写入：同步交易日历时采用批量插入，减少数据库往返
- 余额与份额计算：基于最新快照与增量计算，避免全量扫描
- **新增** CASH交易配对验证：通过transfer_group索引优化配对查询性能
- **新增** 交易预览缓存：预览结果可在短时间内缓存，减少重复计算
- 建议：
  - 前端对高频查询设置合理缓存时间
  - 后端对热点查询增加索引（如按portfolio_code、status、trade_date、transfer_group）
  - 交易预览接口考虑添加短期缓存机制

## 故障排除指南
常见错误与处理：
- 非交易日提交：返回"非交易日，请等待交易日再提交"
- 组合未激活：返回"组合未激活"
- 产品不存在：返回"Product not found"
- 买入金额无效或超可用现金：返回"买入金额必须大于0"或"买入金额超过可用现金"
- 卖出份额无效或超可用份额：返回"卖出份额必须大于0"或"卖出份额超过可用份额"
- 状态不符：仅pending可确认/取消，否则返回"仅 pending 状态可确认/取消"
- 场内交易不可取消：返回"场内交易不可取消"
- 净值型产品缺少净值：QDII返回"T日净值尚未同步"，非QDII返回"净值尚未同步"
- **新增** 已确认交易修改失败：返回"已确认的交易不可直接修改，请先取消确认后再修改"
- **新增** 已确认交易删除失败：返回"已确认的交易不可直接删除，请先取消确认后再删除"
- **新增** CASH交易创建失败：返回"CASH_TRADE_FORBIDDEN"错误，表示不允许直接创建裸CASH交易
- **新增** 缺少transfer_group：返回"transfer_group是CASH交易的必填字段"
- **新增** 配对交易不完整：返回"配对交易不完整，请确保同一transfer_group内的交易成对出现"
- **新增** 交易预览失败：检查交易ID是否存在，验证网络连接状态

定位参考：
- 错误抛出位置与消息定义见 [backend/app/routers/trades.py:298-336](file://backend/app/routers/trades.py#L298-L336)、[L364-L374]、[L428-L432]、[L516-L528]、[L458-L464]、[L546-L553]、[L573-L580]
- 交易日判断见 [backend/app/services/trading_calendar_service.py:110-124](file://backend/app/services/trading_calendar_service.py#L110-L124)
- CASH交易验证逻辑见 [backend/app/routers/trades.py:292-402](file://backend/app/routers/trades.py#L292-L402)
- 交易预览功能见 [backend/app/routers/trades.py:415-416](file://backend/app/routers/trades.py#L415-L416)

**章节来源**
- [backend/app/routers/trades.py:298-336](file://backend/app/routers/trades.py#L298-L336)
- [backend/app/routers/trades.py:364-374](file://backend/app/routers/trades.py#L364-L374)
- [backend/app/routers/trades.py:428-432](file://backend/app/routers/trades.py#L428-L432)
- [backend/app/routers/trades.py:516-528](file://backend/app/routers/trades.py#L516-L528)
- [backend/app/routers/trades.py:458-464](file://backend/app/routers/trades.py#L458-L464)
- [backend/app/routers/trades.py:546-553](file://backend/app/routers/trades.py#L546-L553)
- [backend/app/routers/trades.py:573-580](file://backend/app/routers/trades.py#L573-L580)
- [backend/app/services/trading_calendar_service.py:110-124](file://backend/app/services/trading_calendar_service.py#L110-L124)
- [backend/app/routers/trades.py:415-416](file://backend/app/routers/trades.py#L415-L416)

## 结论
交易管理API提供了完整的调仓交易生命周期管理：从创建（买入/卖出）、到确认（净值型与非净值型差异化处理）、再到取消与删除。通过严格的权限控制、交易日校验、可用资金/份额计算与状态机管理，确保交易安全与一致性。

**重要更新** 新增的交易预览功能为用户提供了在执行交易前的验证能力，提升了系统的易用性和安全性。用户可以通过预览接口在不产生实际数据变更的情况下验证交易参数和预估结果，大大改善了用户体验。

同时，新增的CASH交易强制配对验证机制进一步强化了资金管理的严谨性，通过禁止直接创建裸CASH交易，确保所有现金流动都通过受控路径进行。这一改进为复杂的金融交易管理提供了必要的数据完整性和审计追踪能力。

安全验证机制也强化了数据完整性保护，防止对已确认交易进行直接修改或删除操作。管理员需要遵循"先取消确认，再进行修改或删除"的工作流程，这为复杂的金融交易管理提供了必要的安全保障。

前端通过标准化的Hooks与类型定义，简化了集成与调试，并支持新的预览功能。

## 附录

### 接口清单与示例

- 交易列表
  - 方法：GET
  - 路径：/api/trades
  - 查询参数：portfolio_code、page、page_size
  - 示例响应：items、total、page、page_size
  - 参考：[backend/app/routers/trades.py:271-289](file://backend/app/routers/trades.py#L271-L289)

- 单个交易
  - 方法：GET
  - 路径：/api/trades/{id}
  - 权限：登录用户
  - 示例响应：TradeResponse
  - 参考：[backend/app/routers/trades.py:405-414](file://backend/app/routers/trades.py#L405-L414)

- **新增** 交易预览
  - 方法：GET
  - 路径：/api/trades/{id}/preview
  - 权限：登录用户
  - 功能：验证交易参数并返回预估结果
  - 示例响应：TradePreviewResponse（包含预估金额、费用、份额等信息）
  - 参考：[backend/app/routers/trades.py:415-416](file://backend/app/routers/trades.py#L415-L416)

- 创建交易
  - 方法：POST
  - 路径：/api/trades
  - 权限：管理员
  - 请求体：TradeCreate（买入需amount，卖出需shares）
  - **新增** CASH交易要求：必须提供有效的transfer_group字段
  - 示例响应：TradeResponse（status=pending）
  - 参考：[backend/app/routers/trades.py:292-402](file://backend/app/routers/trades.py#L292-L402)

- 更新交易
  - 方法：PUT
  - 路径：/api/trades/{id}
  - 权限：管理员
  - 请求体：TradeUpdate（部分字段）
  - 安全验证：已确认交易不可直接修改
  - 示例响应：TradeResponse
  - 参考：[backend/app/routers/trades.py:535-561](file://backend/app/routers/trades.py#L535-L561)

- 删除交易
  - 方法：DELETE
  - 路径：/api/trades/{id}
  - 权限：管理员
  - 安全验证：已确认交易不可直接删除
  - 示例响应：成功消息
  - 参考：[backend/app/routers/trades.py:563-585](file://backend/app/routers/trades.py#L563-L585)

- 确认交易
  - 方法：POST
  - 路径：/api/trades/{id}/confirm
  - 查询参数：confirm_date（可选）、price（可选）
  - 权限：管理员
  - 示例响应：包含message、id、portfolio_code、trade_type、status、confirm_date与trade对象
  - 参考：[backend/app/routers/trades.py:417-504](file://backend/app/routers/trades.py#L417-504)

- 取消交易
  - 方法：POST
  - 路径：/api/trades/{id}/cancel
  - 权限：管理员
  - 示例响应：成功消息
  - 参考：[backend/app/routers/trades.py:507-532](file://backend/app/routers/trades.py#L507-L532)

### 数据模型与字段说明
- Trade模型字段：id、portfolio_code、platform_code、product_code、market、trade_type、shares、amount、price、fee、actual_amount、trade_date、confirm_date、status、notes、created_at、updated_at
  - 参考：[backend/app/models/trade.py:5-32](file://backend/app/models/trade.py#L5-32)
- Trade Schema：TradeBase/TradeCreate/TradeUpdate/TradeResponse
  - 参考：[backend/app/schemas/trade.py:6-45](file://backend/app/schemas/trade.py#L6-L45)
- Product模型：product_type、confirm_days、is_qdii
  - 参考：[backend/app/models/product.py:11-14](file://backend/app/models/product.py#L11-L14)
- Portfolio模型：status
  - 参考：[backend/app/models/portfolio.py](file://backend/app/models/portfolio.py#L11)
- PortfolioPosition模型：shares、snapshot_date
  - 参考：[backend/app/models/portfolio_position.py:13-20](file://backend/app/models/portfolio_position.py#L13-L20)
- Subscription模型：sub_type、amount、shares、unit_price、apply_date、confirm_date、status
  - 参考：[backend/app/models/subscription.py:11-17](file://backend/app/models/subscription.py#L11-L17)
- PriceRecord模型：unit_price、pre_close、pct_change、net_asset
  - 参考：[backend/app/models/price_record.py:12-16](file://backend/app/models/price_record.py#L12-L16)

### CASH交易配对验证规则
**新增** CASH交易现在需要遵循严格的配对验证规则：

- **transfer_group字段**：所有CASH交易必须提供唯一的配对组标识符
- **配对完整性**：同一transfer_group内的交易必须成对出现，确保资金平衡
- **受控路径**：只能通过申购赎回、基金再平衡或跨平台转账三种方式创建
- **错误处理**：违反规则的请求将返回CASH_TRADE_FORBIDDEN错误

### 交易预览响应模型
**新增** TradePreviewResponse包含以下字段：
- trade_id: 交易ID
- portfolio_code: 组合代码
- product_code: 产品代码
- trade_type: 交易类型
- estimated_amount: 预估金额
- estimated_shares: 预估份额
- estimated_fee: 预估费用
- estimated_actual_amount: 预估实际金额
- validation_status: 验证状态（valid/invalid）
- warnings: 警告信息列表
- errors: 错误信息列表

**章节来源**
- [backend/app/routers/trades.py:292-402](file://backend/app/routers/trades.py#L292-L402)
- [backend/app/models/trade.py:5-32](file://backend/app/models/trade.py#L5-L32)
- [backend/app/schemas/trade.py:6-45](file://backend/app/schemas/trade.py#L6-L45)
- [backend/app/routers/trades.py:415-416](file://backend/app/routers/trades.py#L415-L416)