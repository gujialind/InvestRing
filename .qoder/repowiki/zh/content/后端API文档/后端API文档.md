# 后端API文档

<cite>
**本文档引用的文件**
- [backend/app/main.py](file://backend/app/main.py)
- [backend/app/config.py](file://backend/app/config.py)
- [backend/app/dependencies.py](file://backend/app/dependencies.py)
- [backend/app/utils/security.py](file://backend/app/utils/security.py)
- [backend/app/routers/auth.py](file://backend/app/routers/auth.py)
- [backend/app/routers/investors.py](file://backend/app/routers/investors.py)
- [backend/app/routers/portfolios.py](file://backend/app/routers/portfolios.py)
- [backend/app/routers/products.py](file://backend/app/routers/products.py)
- [backend/app/routers/platforms.py](file://backend/app/routers/platforms.py)
- [backend/app/routers/positions.py](file://backend/app/routers/positions.py)
- [backend/app/routers/trades.py](file://backend/app/routers/trades.py)
- [backend/app/routers/snapshots.py](file://backend/app/routers/snapshots.py)
- [backend/app/routers/tasks.py](file://backend/app/routers/tasks.py)
- [backend/app/routers/subscriptions.py](file://backend/app/routers/subscriptions.py)
- [backend/app/routers/data_sources.py](file://backend/app/routers/data_sources.py)
- [backend/app/routers/market_data.py](file://backend/app/routers/market_data.py)
- [backend/app/routers/logs.py](file://backend/app/routers/logs.py)
- [backend/app/routers/notifications.py](file://backend/app/routers/notifications.py)
- [backend/app/routers/share_change_events.py](file://backend/app/routers/share_change_events.py)
- [backend/app/routers/trading_calendar.py](file://backend/app/routers/trading_calendar.py)
- [backend/export_openapi.py](file://backend/export_openapi.py)
- [backend/openapi.json](file://backend/openapi.json)
- [backend/nginx/nginx.conf](file://backend/nginx/nginx.conf)
- [backend/requirements.txt](file://backend/requirements.txt)
- [backend/app/models/share_change_event.py](file://backend/app/models/share_change_event.py)
- [backend/app/schemas/share_change_event.py](file://backend/app/schemas/share_change_event.py)
- [backend/cli/commands/share_events.py](file://backend/cli/commands/share_events.py)
- [frontend/src/types/share-change-event.ts](file://frontend/src/types/share-change-event.ts)
- [Docs/init_data.sql](file://Docs/init_data.sql)
</cite>

## 更新摘要
**所做更改**
- 新增交易日历API端点（GET /api/trading-calendar/next, prev, is-open）用于查询下一个交易日、上一个交易日和交易状态
- 增强快照管理系统，支持批量删除和干运行模式
- 扩展投资组合聚合端点，新增total_value/cumulative_return/investor_count指标
- 新增持仓可用份额查询端点（GET /api/positions/portfolio/{portfolio_code}/product/{product_code}/available-shares）
- 改进任务管理，新增单个任务查询端点

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构总览](#架构总览)
5. [详细组件分析](#详细组件分析)
6. [OpenAPI规范管理](#openapi规范管理)
7. [依赖分析](#依赖分析)
8. [性能考虑](#性能考虑)
9. [故障排除指南](#故障排除指南)
10. [结论](#结论)
11. [附录](#附录)

## 简介
本文件为 InvestRing 后端的完整 API 文档，覆盖认证系统、投资人管理、投资组合管理、产品管理、持仓管理、交易管理、快照系统、任务管理、数据源配置、市场数据、日志管理、通知管理、份额变动事件、交易日历等模块。文档提供每个 API 的 HTTP 方法、URL 模式、请求/响应模式、认证方式与权限控制、错误码说明、请求与响应示例路径、版本管理与兼容性策略、常见使用场景与最佳实践。

**更新** 本次更新新增了交易日历查询功能、增强了快照管理的批量操作能力、扩展了投资组合聚合指标、完善了持仓管理和任务管理功能，进一步提升了系统的完整性和易用性。

## 项目结构
后端基于 FastAPI 构建，采用模块化路由组织，核心入口在主应用中注册各模块路由，并统一处理 CORS 与数据库初始化。认证与权限通过依赖注入与安全工具实现，配置集中于配置模块。新增OpenAPI规范自动生成与管理功能和完整的通知系统API。

```mermaid
graph TB
A["应用入口<br/>main.py"] --> B["认证路由<br/>routers/auth.py"]
A --> C["投资人路由<br/>routers/investors.py"]
A --> D["组合路由<br/>routers/portfolios.py"]
A --> E["产品路由<br/>routers/products.py"]
A --> F["平台路由<br/>routers/platforms.py"]
A --> G["交易路由<br/>routers/trades.py"]
A --> H["持仓路由<br/>routers/positions.py"]
A --> I["订阅路由<br/>routers/subscriptions.py"]
A --> J["快照路由<br/>routers/snapshots.py"]
A --> K["任务路由<br/>routers/tasks.py"]
A --> L["通用依赖与安全<br/>dependencies.py / utils/security.py"]
A --> M["配置<br/>config.py"]
A --> N["数据源路由<br/>routers/data_sources.py"]
A --> O["市场数据路由<br/>routers/market_data.py"]
A --> P["日志路由<br/>routers/logs.py"]
A --> Q["通知路由<br/>routers/notifications.py"]
A --> R["份额事件路由<br/>routers/share_change_events.py"]
A --> S["交易日历路由<br/>routers/trading_calendar.py"]
A --> T["OpenAPI规范<br/>export_openapi.py / openapi.json"]
```

**图表来源**
- [backend/app/main.py:17-48](file://backend/app/main.py#L17-L48)
- [backend/app/routers/auth.py:25](file://backend/app/routers/auth.py#L25)
- [backend/app/routers/investors.py:11](file://backend/app/routers/investors.py#L11)
- [backend/app/routers/portfolios.py:15](file://backend/app/routers/portfolios.py#L15)
- [backend/app/routers/products.py:9](file://backend/app/routers/products.py#L9)
- [backend/app/routers/platforms.py:9](file://backend/app/routers/platforms.py#L9)
- [backend/app/routers/trades.py:108](file://backend/app/routers/trades.py#L108)
- [backend/app/routers/positions.py:16](file://backend/app/routers/positions.py#L16)
- [backend/app/routers/subscriptions.py:16](file://backend/app/routers/subscriptions.py#L16)
- [backend/app/routers/snapshots.py:25](file://backend/app/routers/snapshots.py#L25)
- [backend/app/routers/tasks.py:16](file://backend/app/routers/tasks.py#L16)
- [backend/app/routers/data_sources.py:11](file://backend/app/routers/data_sources.py#L11)
- [backend/app/routers/market_data.py:1](file://backend/app/routers/market_data.py#L1)
- [backend/app/routers/logs.py:1](file://backend/app/routers/logs.py#L1)
- [backend/app/routers/notifications.py:1](file://backend/app/routers/notifications.py#L1)
- [backend/app/routers/share_change_events.py:1](file://backend/app/routers/share_change_events.py#L1)
- [backend/app/routers/trading_calendar.py:1](file://backend/app/routers/trading_calendar.py#L1)
- [backend/export_openapi.py:1](file://backend/export_openapi.py#L1)
- [backend/openapi.json:1](file://backend/openapi.json#L1)

## 核心组件
- 应用入口与路由注册：在主应用中注册认证、投资人、组合、产品、平台、交易、持仓、订阅、快照、任务、数据源、市场数据、日志、通知、份额事件、交易日历等路由，并启用 CORS。
- 认证与权限：通过 HTTP Bearer Token 进行认证，支持令牌黑名单、账户锁定与失败追踪；提供普通用户与管理员权限依赖。
- 安全工具：密码哈希、JWT 编解码、令牌黑名单维护、登录失败锁定策略。
- 配置中心：集中管理数据库连接、密钥、Tushare Token、调试开关等。
- **OpenAPI规范管理**：自动生成和导出OpenAPI规范，支持Apifox等工具导入，现已增强对投资组合相关端点的schema定义。
- **增强错误处理**：新增PRICE_NAV_MISMATCH错误代码，专门处理场外基金净值与提供价格不一致的业务场景。
- **通知系统**：完整的通知管理功能，支持通知查询、标记已读和批量操作。
- **净值覆盖率验证**：新增nav-coverage端点，支持投资组合净值数据的完整性检查和覆盖率分析。
- **交易日历增强**：新增next、prev、is-open端点，提供更灵活的交易日查询功能。

**章节来源**
- [backend/app/main.py:17-48](file://backend/app/main.py#L17-L48)
- [backend/app/dependencies.py:49-137](file://backend/app/dependencies.py#L49-L137)
- [backend/app/utils/security.py:15-103](file://backend/app/utils/security.py#L15-L103)
- [backend/app/config.py:5-36](file://backend/app/config.py#L5-L36)
- [backend/export_openapi.py:1](file://backend/export_openapi.py#L1)

## 架构总览
下图展示 API 路由与核心依赖的关系，体现认证、权限、安全与业务模块之间的交互，以及新增的OpenAPI规范管理流程、增强的错误处理机制、完整的通知系统功能和净值覆盖率验证功能。

```mermaid
graph TB
subgraph "认证与安全"
Sec["安全工具<br/>utils/security.py"]
Dep["通用依赖<br/>dependencies.py"]
Err["错误处理<br/>Enhanced Error Handling"]
end
subgraph "业务路由"
AuthR["认证路由<br/>routers/auth.py"]
InvR["投资人路由<br/>routers/investors.py"]
PftR["组合路由<br/>routers/portfolios.py"]
ProR["产品路由<br/>routers/products.py"]
PlaR["平台路由<br/>routers/platforms.py"]
TrdR["交易路由<br/>routers/trades.py"]
PosR["持仓路由<br/>routers/positions.py"]
SubR["订阅路由<br/>routers/subscriptions.py"]
SnpR["快照路由<br/>routers/snapshots.py"]
TskR["任务路由<br/>routers/tasks.py"]
DataR["数据源路由<br/>routers/data_sources.py"]
MktR["市场数据路由<br/>routers/market_data.py"]
LogR["日志路由<br/>routers/logs.py"]
NotiR["通知路由<br/>routers/notifications.py"]
ShareR["份额事件路由<br/>routers/share_change_events.py"]
CalR["交易日历路由<br/>routers/trading_calendar.py"]
end
subgraph "OpenAPI规范管理"
Exp["导出脚本<br/>export_openapi.py"]
Spec["规范文件<br/>openapi.json"]
Nginx["Nginx配置<br/>nginx.conf"]
end
Main["应用入口<br/>main.py"] --> AuthR
Main --> InvR
Main --> PftR
Main --> ProR
Main --> PlaR
Main --> TrdR
Main --> PosR
Main --> SubR
Main --> SnpR
Main --> TskR
Main --> DataR
Main --> MktR
Main --> LogR
Main --> NotiR
Main --> ShareR
Main --> CalR
AuthR --> Sec
AuthR --> Dep
AuthR --> Err
InvR --> Dep
PftR --> Dep
ProR --> Dep
PlaR --> Dep
TrdR --> Dep
TrdR --> Err
PosR --> Dep
SubR --> Dep
SnpR --> Dep
TskR --> Dep
DataR --> Dep
MktR --> Dep
MktR --> NavCoverage["净值覆盖率验证<br/>nav-coverage端点"]
LogR --> Dep
NotiR --> Dep
ShareR --> Dep
CalR --> Dep
Exp --> Spec
Nginx --> Spec
```

**图表来源**
- [backend/app/main.py:32-48](file://backend/app/main.py#L32-L48)
- [backend/app/routers/auth.py:15-21](file://backend/app/routers/auth.py#L15-L21)
- [backend/app/dependencies.py:9](file://backend/app/dependencies.py#L9)
- [backend/app/utils/security.py:8](file://backend/app/utils/security.py#L8)
- [backend/export_openapi.py:1](file://backend/export_openapi.py#L1)
- [backend/openapi.json:1](file://backend/openapi.json#L1)
- [backend/nginx/nginx.conf:105](file://backend/nginx/nginx.conf#L105)

## 详细组件分析

### 认证系统
- 认证方式：HTTP Bearer Token（JWT）。登录成功后返回 token 与过期时间，后续请求在 Authorization 头中携带 Bearer token。
- 权限控制：普通用户依赖 get_current_user，管理员依赖 get_current_admin；支持令牌黑名单与账户锁定。
- 错误码：包含 INVALID_CREDENTIALS、ACCOUNT_LOCKED、FORBIDDEN、INVALID_TOKEN 等。

接口清单
- POST /api/auth/login
  - 请求体：LoginRequest（包含 code、password）
  - 响应体：LoginResponse（token、expires_at、user）
  - 权限：匿名
  - 示例路径：[登录请求体示例:30-30](file://backend/app/routers/auth.py#L30-L30)，[登录响应示例:87-95](file://backend/app/routers/auth.py#L87-L95)
- POST /api/auth/logout
  - 请求体：无
  - 响应体：{"message": "..."}
  - 权限：需要认证
  - 示例路径：[登出示例:98-119](file://backend/app/routers/auth.py#L98-L119)
- PUT /api/auth/password
  - 请求体：ChangePasswordRequest（target_code 可选、old_password、new_password）
  - 响应体：{"message": "..."}
  - 权限：需要认证；admin 可改任意用户密码，viewer 只能改自己且需旧密码
  - 示例路径：[改密请求示例:122-128](file://backend/app/routers/auth.py#L122-L128)，[改密响应示例:185-185](file://backend/app/routers/auth.py#L185-L185)

**章节来源**
- [backend/app/routers/auth.py:29-186](file://backend/app/routers/auth.py#L29-L186)
- [backend/app/dependencies.py:49-137](file://backend/app/dependencies.py#L49-L137)
- [backend/app/utils/security.py:29-46](file://backend/app/utils/security.py#L29-L46)

### 投资人管理
- 权限：仅管理员
- 接口清单
  - GET /api/investors
    - 查询参数：page、page_size、可选 status（组合管理中使用）
    - 响应体：分页对象（items、total、page、page_size）
    - 示例路径：[投资人列表示例:14-29](file://backend/app/routers/investors.py#L14-L29)
  - POST /api/investors
    - 请求体：InvestorCreate（code、name、phone、email、password）
    - 响应体：InvestorResponse
    - 示例路径：[创建投资人示例:32-53](file://backend/app/routers/investors.py#L32-53)
  - GET /api/investors/{code}
    - 响应体：InvestorResponse
    - 示例路径：[获取投资人示例:56-65](file://backend/app/routers/investors.py#L56-65)
  - PUT /api/investors/{code}
    - 请求体：InvestorUpdate（可选字段）
    - 响应体：InvestorResponse
    - 示例路径：[更新投资人示例:68-88](file://backend/app/routers/investors.py#L68-88)
  - DELETE /api/investors/{code}
    - 响应体：{"message": "..."}
    - 示例路径：[删除投资人示例:91-119](file://backend/app/routers/investors.py#L91-L119)

**章节来源**
- [backend/app/routers/investors.py:14-120](file://backend/app/routers/investors.py#L14-L120)

### 投资组合管理
- 权限：GET /api/portfolios 与 GET /api/portfolios/{code} 对普通用户开放；其余对管理员开放
- 接口清单
  - GET /api/portfolios
    - 查询参数：status、page、page_size
    - 响应体：分页对象
    - 示例路径：[组合列表示例:18-36](file://backend/app/routers/portfolios.py#L18-L36)
  - POST /api/portfolios
    - 请求体：PortfolioCreate
    - 响应体：PortfolioResponse
    - 示例路径：[创建组合示例:39-58](file://backend/app/routers/portfolios.py#L39-L58)
  - GET /api/portfolios/{code}
    - 响应体：PortfolioResponse
    - 示例路径：[获取组合示例:61-70](file://backend/app/routers/portfolios.py#L61-L70)
  - PUT /api/portfolios/{code}
    - 请求体：PortfolioUpdate
    - 响应体：PortfolioResponse
    - 示例路径：[更新组合示例:73-89](file://backend/app/routers/portfolios.py#L73-L89)
  - POST /api/portfolios/{code}/close
    - 响应体：{"message": "..."}
    - 示例路径：[关闭组合示例:92-131](file://backend/app/routers/portfolios.py#L92-L131)
  - POST /api/portfolios/{code}/reactivate
    - 响应体：{"message": "..."}
    - 示例路径：[重新激活组合示例:134-156](file://backend/app/routers/portfolios.py#L134-L156)
  - GET /api/portfolios/{code}/nav-history
    - 查询参数：start_date、end_date
    - 响应体：包含日期、单位净值、总值、总份额的历史数组，使用NavHistoryRecord模型
    - **更新** 响应模型现在包含完整的NavHistoryRecord结构，提供更准确的净值历史数据结构
    - 示例路径：[净值历史示例:159-191](file://backend/app/routers/portfolios.py#L159-L191)
  - GET /api/portfolios/{code}/returns
    - 响应体：累计收益、年化收益、初始/当前净值、持有天数
    - 示例路径：[收益统计示例:194-241](file://backend/app/routers/portfolios.py#L194-L241)
  - GET /api/portfolios/{code}/cash-flow
    - 响应体：流入、流出、净流入
    - 示例路径：[现金流示例:244-275](file://backend/app/routers/portfolios.py#L244-L275)
  - **新增** GET /api/portfolios/{code}/aggregation
    - 查询参数：start_date、end_date
    - 响应体：包含total_value（组合总值）、cumulative_return（累计收益率）、investor_count（投资者数量）等聚合指标
    - 功能：提供投资组合的综合统计分析，支持按时间范围聚合数据
    - 示例路径：[组合聚合示例:278-320](file://backend/app/routers/portfolios.py#L278-L320)

**更新** 投资组合聚合端点新增total_value、cumulative_return、investor_count等关键指标，为投资组合分析提供了更全面的统计数据支持。这些指标可以帮助管理员快速了解投资组合的整体表现和规模。

**章节来源**
- [backend/app/routers/portfolios.py:18-320](file://backend/app/routers/portfolios.py#L18-L320)

### 产品管理
- 权限：管理员
- 接口清单
  - GET /api/products
    - 查询参数：product_type、page、page_size
    - 响应体：分页对象
    - 示例路径：[产品列表示例:27-45](file://backend/app/routers/products.py#L27-L45)
  - POST /api/products
    - 请求体：ProductCreate
    - 响应体：ProductResponse
    - 示例路径：[创建产品示例:48-76](file://backend/app/routers/products.py#L48-L76)
  - GET /api/products/{code}/{market}
    - 响应体：ProductResponse
    - 示例路径：[获取产品示例:79-92](file://backend/app/routers/products.py#L79-L92)
  - PUT /api/products/{code}/{market}
    - 请求体：ProductUpdate
    - 响应体：ProductResponse
    - 示例路径：[更新产品示例:95-122](file://backend/app/routers/products.py#L95-L122)
  - DELETE /api/products/{code}/{market}
    - 响应体：{"message": "..."}
    - 示例路径：[删除产品示例:125-141](file://backend/app/routers/products.py#L125-L141)

**章节来源**
- [backend/app/routers/products.py:27-142](file://backend/app/routers/products.py#L27-L142)

### 平台管理
- 权限：GET 对普通用户开放；其余对管理员开放
- 接口清单
  - GET /api/platforms
    - 查询参数：page、page_size
    - 响应体：分页对象
    - 示例路径：[平台列表示例:12-27](file://backend/app/routers/platforms.py#L12-L27)
  - POST /api/platforms
    - 请求体：PlatformCreate
    - 响应体：PlatformResponse
    - 示例路径：[创建平台示例:30-44](file://backend/app/routers/platforms.py#L30-L44)
  - GET /api/platforms/{code}
    - 响应体：PlatformResponse
    - 示例路径：[获取平台示例:47-55](file://backend/app/routers/platforms.py#L47-L55)
  - PUT /api/platforms/{code}
    - 请求体：PlatformUpdate
    - 响应体：PlatformResponse
    - 示例路径：[更新平台示例:59-75](file://backend/app/routers/platforms.py#L59-L75)
  - DELETE /api/platforms/{code}
    - 响应体：{"message": "..."}
    - 示例路径：[删除平台示例:78-90](file://backend/app/routers/platforms.py#L78-L90)

**章节来源**
- [backend/app/routers/platforms.py:12-91](file://backend/app/routers/platforms.py#L12-L91)

### 持仓管理
- 权限：GET 对普通用户开放；其余对管理员开放
- 接口清单
  - GET /api/positions
    - 查询参数：portfolio_code、snapshot_date、page、page_size
    - 响应体：分页对象（默认返回最新快照）
    - 示例路径：[持仓列表示例:180-218](file://backend/app/routers/positions.py#L180-L218)
  - POST /api/positions
    - 请求体：PositionCreate
    - 响应体：PositionResponse
    - 示例路径：[创建持仓示例:221-231](file://backend/app/routers/positions.py#L221-L231)
  - GET /api/positions/{id}
    - 响应体：PositionResponse
    - 示例路径：[获取持仓示例:234-243](file://backend/app/routers/positions.py#L234-L243)
  - PUT /api/positions/{id}
    - 请求体：PositionUpdate
    - 响应体：PositionResponse
    - 示例路径：[更新持仓示例:246-262](file://backend/app/routers/positions.py#L246-L262)
  - DELETE /api/positions/{id}
    - 响应体：{"message": "..."}
    - 示例路径：[删除持仓示例:265-277](file://backend/app/routers/positions.py#L265-L277)
  - GET /api/positions/portfolio/{portfolio_code}/available-cash
    - 响应体：{"portfolio_code": "...", "available_cash": number}
    - 示例路径：[可用现金示例:280-293](file://backend/app/routers/positions.py#L280-L293)
  - **新增** GET /api/positions/portfolio/{portfolio_code}/product/{product_code}/available-shares
    - 查询参数：market（可选）
    - 响应体：{"portfolio_code": "...", "product_code": "...", "market": "...", "available_shares": number}
    - 功能：查询指定产品在投资组合中的可用份额，支持按市场筛选
    - 示例路径：[可用份额查询示例:296-316](file://backend/app/routers/positions.py#L296-L316)
  - POST /api/positions/portfolio/{portfolio_code}/cash-position
    - 请求体：CashPositionUpdate（包含 platform_code、amount、update_date 可选）
    - 响应体：操作结果
    - 权限：管理员；仅交易日；必须指定平台代码；CASH 产品金额更新
    - 示例路径：[更新现金头寸示例:319-409](file://backend/app/routers/positions.py#L319-L409)

**更新** 新增available-shares端点：该端点专门用于查询投资组合中特定产品的可用份额，支持按市场参数进行筛选。这对于交易前的可用性检查非常有用，可以确保交易的可行性。

**章节来源**
- [backend/app/routers/positions.py:180-410](file://backend/app/routers/positions.py#L180-L410)

### 交易管理
- 权限：除查询外多为管理员；交易日校验与可用性计算贯穿流程
- 接口清单
  - GET /api/trades
    - 查询参数：portfolio_code、page、page_size
    - 响应体：分页对象（按创建时间倒序）
    - 示例路径：[交易列表示例:271-289](file://backend/app/routers/trades.py#L271-L289)
  - POST /api/trades
    - 请求体：TradeCreate（buy/sell 类型、金额/份额、价格、费用、交易日期等）
    - 响应体：TradeResponse（状态默认 pending）
    - 权限：管理员；交易日校验；可用现金/份额校验；自动计算份额与金额
    - 示例路径：[创建交易示例:292-402](file://backend/app/routers/trades.py#L292-L402)
  - GET /api/trades/{id}
    - 响应体：TradeResponse
    - 示例路径：[获取交易示例:405-414](file://backend/app/routers/trades.py#L405-L414)
  - POST /api/trades/{id}/confirm
    - 查询参数：confirm_date（可选）、price（可选）
    - 响应体：确认结果与 TradeResponse
    - 权限：管理员；净值型产品需净值；非净值型可手动指定价格
    - **新增错误码**：PRICE_NAV_MISMATCH - 当提供的价格与基金净值不一致时返回此错误
    - 示例路径：[确认交易示例:417-504](file://backend/app/routers/trades.py#L417-L504)
  - POST /api/trades/{id}/cancel
    - 响应体：{"message": "..."}
    - 权限：管理员；仅场外 pending 可取消
    - 示例路径：[取消交易示例:507-532](file://backend/app/routers/trades.py#L507-L532)
  - PUT /api/trades/{id}
    - 请求体：TradeUpdate
    - 响应体：TradeResponse
    - 示例路径：[更新交易示例:535-551](file://backend/app/routers/trades.py#L535-L551)
  - DELETE /api/trades/{id}
    - 响应体：{"message": "..."}
    - 示例路径：[删除交易示例:554-566](file://backend/app/routers/trades.py#L554-L566)

**更新** 新增PRICE_NAV_MISMATCH错误码：在处理场外基金交易确认时，如果客户端提供的价格与系统获取的基金净值不一致，将返回此错误码。这有助于确保交易价格的准确性和一致性。

**章节来源**
- [backend/app/routers/trades.py:271-567](file://backend/app/routers/trades.py#L271-L567)

### 快照系统
- 版本：/api/v1（快照管理路由前缀为 /api/v1）
- 权限：生成/重算/删除/预检为管理员；查询组合快照状态对普通用户开放
- 接口清单
  - POST /api/v1/snapshots/generate
    - 请求体：SnapshotGenerateRequest（portfolio_code、target_date）
    - 响应体：SnapshotGenerationResult
    - 示例路径：[生成快照示例:28-55](file://backend/app/routers/snapshots.py#L28-L55)
  - POST /api/v1/snapshots/recalculate
    - 请求体：SnapshotRecalculateRequest（portfolio_code、start_date、end_date、force）
    - 响应体：RecalculationResult
    - 示例路径：[重算快照示例:58-87](file://backend/app/routers/snapshots.py#L58-L87)
  - GET /api/v1/snapshots/validation
    - 查询参数：portfolio_code、target_date
    - 响应体：SnapshotValidationResult
    - 示例路径：[依赖预检示例:90-111](file://backend/app/routers/snapshots.py#L90-L111)
  - GET /api/v1/snapshots/portfolios/{code}/status
    - 响应体：SnapshotStatusResponse（最新/最早快照日期、总数、缺失日期列表）
    - 示例路径：[快照状态示例:114-157](file://backend/app/routers/snapshots.py#L114-L157)
  - **新增** DELETE /api/v1/snapshots/batch
    - 请求体：BatchDeleteRequest（portfolio_codes、date_range、dry_run）
    - 响应体：BatchDeleteResult
    - 功能：批量删除多个投资组合的快照，支持干运行模式进行预检查
    - 权限：管理员；支持dry_run参数进行预检查而不实际执行删除
    - 示例路径：[批量删除快照示例:160-200](file://backend/app/routers/snapshots.py#L160-L200)
  - DELETE /api/v1/snapshots/{portfolio_code}/{snapshot_date}
    - 响应体：{"success": true, "message": "..."}
    - 示例路径：[删除快照示例:203-230](file://backend/app/routers/snapshots.py#L203-L230)

**更新** 新增批量删除功能：新的batch端点支持一次性删除多个投资组合的快照，并提供dry_run模式用于预检查。这大大提高了批量操作的效率和安全性，避免误删风险。

**章节来源**
- [backend/app/routers/snapshots.py:28-230](file://backend/app/routers/snapshots.py#L28-L230)

### 任务管理
- 权限：管理员
- 接口清单
  - GET /api/system/tasks
    - 查询参数：page、page_size
    - 响应体：分页对象
    - 示例路径：[任务列表示例:70-85](file://backend/app/routers/tasks.py#L70-L85)
  - **新增** GET /api/system/tasks/{task_id}
    - 响应体：TaskDetailResponse（包含任务ID、名称、状态、创建时间、执行时间、结果等详细信息）
    - 功能：查询单个任务的详细信息和执行状态
    - 权限：管理员
    - 示例路径：[单个任务查询示例:88-120](file://backend/app/routers/tasks.py#L88-L120)
  - POST /api/system/tasks/{code}/run
    - 响应体：根据任务类型返回不同结果（如净值同步后的统计）
    - 支持任务：trading_calendar_sync、nav_sync、log_cleanup
    - 示例路径：[运行任务示例:123-267](file://backend/app/routers/tasks.py#L123-L267)
  - POST /api/system/tasks/{code}/enable
    - 响应体：{"message": "..."}
    - 示例路径：[启用任务示例:270-282](file://backend/app/routers/tasks.py#L270-L282)
  - POST /api/system/tasks/{code}/disable
    - 响应体：{"message": "..."}
    - 示例路径：[禁用任务示例:285-297](file://backend/app/routers/tasks.py#L285-L297)
  - GET /api/system/tasks/{code}/logs
    - 查询参数：page、page_size
    - 响应体：分页对象（任务执行日志）
    - 示例路径：[任务日志示例:300-322](file://backend/app/routers/tasks.py#L300-L322)

**更新** 新增单个任务查询端点：新的task_id端点允许管理员查询特定任务的详细信息，包括执行状态、创建时间、执行时间等元数据。这为任务监控和管理提供了更好的支持。

**章节来源**
- [backend/app/routers/tasks.py:70-323](file://backend/app/routers/tasks.py#L70-L323)

### 申购赎回
- 权限：GET 对普通用户开放（viewer 仅能看自己的记录）；其余对管理员开放
- 接口清单
  - GET /api/subscriptions
    - 查询参数：portfolio_code、investor_code、page、page_size
    - 响应体：分页对象（按创建时间倒序）
    - 示例路径：[订阅列表示例:88-112](file://backend/app/routers/subscriptions.py#L88-L112)
  - POST /api/subscriptions
    - 请求体：SubscriptionCreate（subscribe/redeem 类型、金额/份额、申请日期）
    - 响应体：SubscriptionResponse（状态默认 pending）
    - 权限：管理员；交易日校验；可用份额校验（赎回）
    - 示例路径：[创建订阅示例:115-199](file://backend/app/routers/subscriptions.py#L115-L199)
  - GET /api/subscriptions/{id}
    - 响应体：SubscriptionResponse
    - 权限：普通用户仅能查看自己的记录
    - 示例路径：[获取订阅示例:202-213](file://backend/app/routers/subscriptions.py#L202-L213)
  - POST /api/subscriptions/{id}/confirm
    - 查询参数：confirm_date（可选）、unit_price（可选）
    - 响应体：确认结果与 SubscriptionResponse
    - 权限：管理员；首次申购净值固定；赎回需提供净值
    - 示例路径：[确认订阅示例:237-320](file://backend/app/routers/subscriptions.py#L237-L320)
  - POST /api/subscriptions/{id}/cancel
    - 响应体：{"message": "..."}
    - 权限：管理员；仅 pending 可取消
    - 示例路径：[取消订阅示例:323-340](file://backend/app/routers/subscriptions.py#L323-L340)
  - PUT /api/subscriptions/{id}
    - 请求体：SubscriptionUpdate
    - 响应体：SubscriptionResponse
    - 示例路径：[更新订阅示例:343-359](file://backend/app/routers/subscriptions.py#L343-L359)
  - DELETE /api/subscriptions/{id}
    - 响应体：{"message": "..."}
    - 示例路径：[删除订阅示例:362-374](file://backend/app/routers/subscriptions.py#L362-L374)

**章节来源**
- [backend/app/routers/subscriptions.py:88-375](file://backend/app/routers/subscriptions.py#L88-L375)

### 数据源配置
- 权限：管理员
- 接口清单
  - GET /api/system/data-sources
    - 响应体：数据源配置列表（包含Tushare、AkShare等）
    - 示例路径：[数据源列表示例:1594-1618](file://backend/app/routers/data_sources.py#L1594-L1618)
  - GET /api/system/data-sources/{name}
    - 响应体：单个数据源配置
    - 示例路径：[数据源详情示例:1619-1674](file://backend/app/routers/data_sources.py#L1619-L1674)
  - PUT /api/system/data-sources/{name}
    - 请求体：DataSourceUpdate
    - 响应体：更新后的数据源配置
    - 示例路径：[更新数据源示例:1675-1700](file://backend/app/routers/data_sources.py#L1675-L1700)

**章节来源**
- [backend/app/routers/data_sources.py:1594-1700](file://backend/app/routers/data_sources.py#L1594-L1700)

### 市场数据
- 权限：管理员
- 接口清单
  - GET /api/market-data/products/{code}/{market}/price-data
    - 查询参数：start_date、end_date、adjust（复权因子）
    - 响应体：价格数据列表
    - 示例路径：[产品价格数据示例:1675-1788](file://backend/app/routers/market_data.py#L1675-L1788)
  - POST /api/market-data/products/{code}/{market}/sync-price-data
    - 请求体：同步请求参数
    - 响应体：同步结果
    - 示例路径：[同步价格数据示例:1789-1854](file://backend/app/routers/market_data.py#L1789-L1854)
  - POST /api/market-data/products/{code}/{market}/sync-history
    - 请求体：历史数据同步参数
    - 响应体：同步结果
    - 示例路径：[同步历史数据示例:1855-1903](file://backend/app/routers/market_data.py#L1855-L1903)
  - POST /api/market-data/portfolios/{portfolio_code}/sync-nav
    - 请求体：净值同步参数
    - 响应体：同步结果
    - 示例路径：[同步组合净值示例:1904-1943](file://backend/app/routers/market_data.py#L1904-L1943)
  - **新增** GET /api/market-data/portfolios/{portfolio_code}/nav-coverage
    - 查询参数：start_date、end_date
    - 响应体：净值覆盖率统计信息（包含覆盖率百分比、缺失日期列表、产品覆盖率分析）
    - 功能：验证投资组合在指定日期范围内的净值数据完整性
    - 示例路径：[净值覆盖率验证示例:1944-2000](file://backend/app/routers/market_data.py#L1944-L2000)

**更新** 新增nav-coverage端点：该端点专门用于净值覆盖率验证，支持对投资组合中所有持仓产品在指定日期范围内的净值数据进行完整性检查。返回的数据包括整体覆盖率百分比、缺失的具体日期列表、以及每个产品的覆盖率分析，帮助管理员及时发现数据缺失问题并进行补充。

**章节来源**
- [backend/app/routers/market_data.py:1675-2000](file://backend/app/routers/market_data.py#L1675-L2000)

### 日志管理
- 权限：管理员
- 接口清单
  - GET /api/logs/system-error-logs
    - 查询参数：level、start_time、end_time、page、page_size
    - 响应体：系统错误日志分页列表
    - 示例路径：[系统错误日志示例:1-200](file://backend/app/routers/logs.py#L1-L200)
  - GET /api/logs/login-logs
    - 查询参数：investor_code、start_time、end_time、page、page_size
    - 响应体：登录日志分页列表
    - 示例路径：[登录日志示例:1-200](file://backend/app/routers/logs.py#L1-L200)
  - GET /api/logs/audit-logs
    - 查询参数：investor_code、operation、start_time、end_time、page、page_size
    - 响应体：审计日志分页列表
    - 示例路径：[审计日志示例:1-200](file://backend/app/routers/logs.py#L1-L200)

**章节来源**
- [backend/app/routers/logs.py:1-200](file://backend/app/routers/logs.py#L1-L200)

### 通知管理
- 权限：管理员
- 接口清单
  - GET /api/notifications
    - 查询参数：investor_code、read_status、start_time、end_time、page、page_size
    - 响应体：通知分页列表
    - 示例路径：[通知列表示例:1-200](file://backend/app/routers/notifications.py#L1-L200)
  - POST /api/notifications/mark-as-read
    - 请求体：标记已读请求
    - 响应体：操作结果
    - 示例路径：[标记已读示例:1-200](file://backend/app/routers/notifications.py#L1-L200)
  - POST /api/notifications/mark-all-as-read
    - 请求体：无
    - 响应体：操作结果
    - 示例路径：[全部标记已读示例:1-200](file://backend/app/routers/notifications.py#L1-L200)

**更新** 新增完整的通知系统API端点，支持通知查询、标记已读和批量操作功能。管理员可以通过这些接口管理系统通知，包括按投资者、阅读状态和时间范围筛选通知，以及批量标记通知为已读状态。

**章节来源**
- [backend/app/routers/notifications.py:1-200](file://backend/app/routers/notifications.py#L1-L200)

### 份额变动事件
- 权限：管理员
- 接口清单
  - GET /api/share-change-events
    - 查询参数：portfolio_code、page、page_size
    - 响应体：份额变动事件分页列表
    - 示例路径：[份额事件列表示例:28-46](file://backend/app/routers/share_change_events.py#L28-L46)
  - POST /api/share-change-events
    - 请求体：ShareChangeEventCreate（包含 portfolio_code、event_type、ex_date、entitlement_date 等）
    - 响应体：创建后的事件
    - 示例路径：[创建份额事件示例:49-77](file://backend/app/routers/share_change_events.py#L49-L77)
  - GET /api/share-change-events/{id}
    - 响应体：单个份额变动事件
    - 示例路径：[份额事件详情示例:80-89](file://backend/app/routers/share_change_events.py#L80-L89)
  - PUT /api/share-change-events/{id}
    - 请求体：ShareChangeEventUpdate
    - 响应体：更新后的事件
    - 示例路径：[更新份额事件示例:151-167](file://backend/app/routers/share_change_events.py#L151-L167)
  - DELETE /api/share-change-events/{id}
    - 响应体：删除结果
    - 示例路径：[删除份额事件示例:170-182](file://backend/app/routers/share_change_events.py#L170-L182)
  - POST /api/share-change-events/{id}/confirm
    - 响应体：确认结果
    - 权限：管理员；校验权益登记日持仓快照存在
    - 示例路径：[确认份额事件示例:92-128](file://backend/app/routers/share_change_events.py#L92-L128)
  - POST /api/share-change-events/{id}/cancel
    - 响应体：{"message": "..."}
    - 权限：管理员；仅 pending 状态可取消
    - 示例路径：[取消份额事件示例:131-148](file://backend/app/routers/share_change_events.py#L131-L148)

**更新** 字段说明：ShareChangeEvent数据模型中的event_date字段已在数据库设计层面重命名为ex_date，但在后端API层仍保持event_date以保持向后兼容。ex_date表示除息/除权日（应用日），是事件生效的关键日期。

**章节来源**
- [backend/app/routers/share_change_events.py:28-183](file://backend/app/routers/share_change_events.py#L28-L183)
- [backend/app/models/share_change_event.py:13](file://backend/app/models/share_change_event.py#L13)
- [backend/app/schemas/share_change_event.py:9](file://backend/app/schemas/share_change_event.py#L9)
- [Docs/init_data.sql:268](file://Docs/init_data.sql#L268)

### 交易日历
- 权限：GET 对普通用户开放；其余对管理员开放
- 接口清单
  - GET /api/trading-calendar
    - 查询参数：year、start_date、end_date、is_open
    - 响应体：交易日历列表
    - 示例路径：[交易日历列表示例:1431-1546](file://backend/app/routers/trading_calendar.py#L1431-L1546)
  - **新增** GET /api/trading-calendar/next
    - 查询参数：from_date（可选，默认为当前日期）
    - 响应体：TradingCalendarResponse（包含下一个交易日的日期、星期几等信息）
    - 功能：查询从指定日期开始的下一个交易日
    - 示例路径：[下一个交易日示例:1547-1560](file://backend/app/routers/trading_calendar.py#L1547-L1560)
  - **新增** GET /api/trading-calendar/prev
    - 查询参数：to_date（可选，默认为当前日期）
    - 响应体：TradingCalendarResponse（包含上一个交易日的日期、星期几等信息）
    - 功能：查询到指定日期为止的上一个交易日
    - 示例路径：[上一个交易日示例:1561-1574](file://backend/app/routers/trading_calendar.py#L1561-L1574)
  - **新增** GET /api/trading-calendar/is-open
    - 查询参数：date（必需）
    - 响应体：{"is_open": boolean, "date": "YYYY-MM-DD"}
    - 功能：检查指定日期是否为交易日
    - 示例路径：[交易状态检查示例:1575-1588](file://backend/app/routers/trading_calendar.py#L1575-L1588)
  - POST /api/trading-calendar/sync
    - 请求体：TradingCalendarSyncRequest
    - 响应体：同步结果
    - 示例路径：[同步交易日历示例:1589-1593](file://backend/app/routers/trading_calendar.py#L1589-L1593)

**更新** 新增三个交易日历查询端点：next端点用于查询下一个交易日，prev端点用于查询上一个交易日，is-open端点用于检查指定日期是否为交易日。这些端点为交易系统和前端界面提供了更灵活的交易日查询能力。

**章节来源**
- [backend/app/routers/trading_calendar.py:1431-1593](file://backend/app/routers/trading_calendar.py#L1431-L1593)

### 认证机制、权限控制与限流策略
- 认证机制
  - 使用 HTTP Bearer Token（JWT），密钥来自配置；登录成功返回 token 与过期时间。
  - 令牌加入黑名单后立即失效；支持账户锁定与失败追踪（连续登录失败锁定）。
- 权限控制
  - 普通用户依赖 get_current_user；管理员依赖 get_current_admin。
  - 部分接口对 viewer 有限制（如订阅查询仅能看到自己的记录）。
- 限流策略
  - Nginx层配置了API限流：limit_req zone=api_limit burst=50 nodelay
  - FastAPI文档路由在生产环境建议关闭，避免暴露内部API细节。

**章节来源**
- [backend/app/utils/security.py:29-46](file://backend/app/utils/security.py#L29-L46)
- [backend/app/dependencies.py:49-137](file://backend/app/dependencies.py#L49-L137)
- [backend/app/config.py:14-16](file://backend/app/config.py#L14-L16)
- [backend/nginx/nginx.conf:85-86](file://backend/nginx/nginx.conf#L85-L86)
- [backend/nginx/nginx.conf:94-103](file://backend/nginx/nginx.conf#L94-L103)

### API 版本管理与向后兼容性
- 版本号：应用版本为 1.0.0。
- 快照模块使用 /api/v1 前缀，便于未来扩展与独立演进。
- 建议：新增接口优先使用新前缀或版本号，保持旧接口稳定；对破坏性变更提供迁移指引与过渡期。

**章节来源**
- [backend/app/main.py:17-21](file://backend/app/main.py#L17-L21)
- [backend/app/routers/snapshots.py:25](file://backend/app/routers/snapshots.py#L25)

### 常见使用场景与最佳实践
- 登录与会话管理
  - 登录成功后缓存 token；登出时将 token 加入黑名单。
  - 密码修改后强制重新登录。
- 交易与风控
  - 交易前进行交易日校验与可用资金/份额校验；确认时根据产品类型自动或手动获取净值。
  - **新增**：处理PRICE_NAV_MISMATCH错误时，应提示用户检查提供的价格是否与当前基金净值一致，或允许系统自动获取最新净值。
- 快照与数据一致性
  - 净值同步完成后自动触发当日快照生成；支持重算与依赖预检。
  - **新增**：使用nav-coverage端点定期检查投资组合净值数据的完整性，确保数据质量。
- 权限最小化
  - viewer 仅能访问自身相关数据；管理员负责系统配置与运营操作。
- **OpenAPI规范管理**
  - 使用export_openapi.py自动生成openapi.json规范文件。
  - 支持Apifox等工具导入，便于API文档管理和团队协作。
  - **更新**：OpenAPI规范现已包含更完整的投资组合相关端点定义，特别是NavHistoryRecord模型的使用。
- **通知系统使用**
  - 管理员可通过通知API管理系统通知，支持按条件筛选和批量操作。
  - 前端应定期轮询通知接口，为用户提供实时通知服务。
- **净值覆盖率验证最佳实践**
  - 建议在每日净值同步任务完成后自动调用nav-coverage端点进行数据完整性检查。
  - 对于覆盖率低于阈值（如95%）的组合，应触发告警通知管理员进行数据补全。
  - 结合快照系统的validation端点，形成完整的数据质量保证体系。
- **交易日历使用最佳实践**
  - 前端在进行交易操作前，应先调用is-open端点检查目标日期是否为交易日。
  - 使用next和prev端点实现智能日期选择，确保用户只能在有效交易日内进行操作。
  - 结合交易日历数据，优化用户体验，避免在非交易日提交无效交易。

**章节来源**
- [backend/app/routers/auth.py:98-186](file://backend/app/routers/auth.py#L98-L186)
- [backend/app/routers/trades.py:292-504](file://backend/app/routers/trades.py#L292-L504)
- [backend/app/routers/tasks.py:199-237](file://backend/app/routers/tasks.py#L199-L237)
- [backend/app/routers/subscriptions.py:237-320](file://backend/app/routers/subscriptions.py#L237-L320)
- [backend/export_openapi.py:1-46](file://backend/export_openapi.py#L1-L46)

## OpenAPI规范管理

### 自动规范生成功能
InvestRing后端提供了完整的OpenAPI规范管理功能，包括自动生成、导出和导入支持。

#### 导出脚本功能
- **export_openapi.py**：提供命令行工具，支持从运行中的后端服务导出OpenAPI规范
- 支持命令行参数：`python export_openapi.py [url] [output_file]`
- 默认URL：`http://localhost:8000/openapi.json`
- 默认输出文件：`openapi.json`

#### 规范文件结构
- **openapi.json**：完整的OpenAPI 3.1.0规范文件
- 包含所有75个API接口的详细描述
- 支持标签分类：认证、投资人管理、组合管理、产品管理等
- 包含完整的请求/响应模式定义
- **新增**：包含nav-coverage端点和交易日历新端点的完整定义和参数说明
- **更新**：规范文件已扩展，涵盖五个高频命令的schema定义，特别是投资组合相关的净值历史、收益统计、现金流等端点的完整数据结构

#### 导入Apifox流程
1. 打开Apifox → 项目设置 → 导入数据
2. 选择 'OpenAPI/Swagger' 格式
3. 上传openapi.json文件
4. 选择导入模式（普通导入/自动合并）
5. 确认导入

#### Nginx配置支持
- Nginx配置中包含`location /openapi.json`路由
- 支持直接访问OpenAPI规范文件
- 生产环境建议配合FastAPI文档路由配置

**章节来源**
- [backend/export_openapi.py:1-46](file://backend/export_openapi.py#L1-L46)
- [backend/openapi.json:1-200](file://backend/openapi.json#L1-L200)
- [backend/nginx/nginx.conf:105-108](file://backend/nginx/nginx.conf#L105-L108)

## 依赖分析
- 外部依赖：FastAPI、SQLAlchemy、Pydantic、JWTS、bcrypt、APScheduler、pandas、numpy、tushare 等。
- 内部依赖：路由模块依赖通用依赖与安全工具；业务模块通过数据库会话与模型交互。
- **OpenAPI依赖**：FastAPI内置OpenAPI生成器，export_openapi.py提供外部导出功能。

```mermaid
graph TB
Req["requirements.txt"] --> FA["FastAPI"]
Req --> SA["SQLAlchemy"]
Req --> PD["Pydantic"]
Req --> JO["python-jose"]
Req --> PB["passlib[bcrypt]"]
Req --> AP["APScheduler"]
Req --> PDa["pandas"]
Req --> NP["numpy"]
Req --> TS["tushare"]
subgraph "OpenAPI支持"
FA --> OA["OpenAPI生成器"]
Exp["export_openapi.py"] --> OA
OA --> Spec["openapi.json"]
end
```

**图表来源**
- [backend/requirements.txt:1-19](file://backend/requirements.txt#L1-L19)
- [backend/export_openapi.py:1](file://backend/export_openapi.py#L1)

**章节来源**
- [backend/requirements.txt:1-19](file://backend/requirements.txt#L1-L19)

## 性能考虑
- 数据库查询优化：分页查询、子查询与聚合查询（如最新快照）需注意索引与排序字段。
- 交易与订阅确认：涉及多表关联与净值查询，建议缓存常用净值与交易日历。
- 任务执行：批量同步与清理任务应分批处理，避免长时间阻塞。
- **OpenAPI规范优化**：规范文件较大（7590行），建议在CI/CD中缓存和版本控制。
- **通知系统性能**：通知查询应支持分页和条件筛选，避免大量数据一次性加载。
- **净值覆盖率验证性能**：nav-coverage端点应支持异步处理和进度反馈，避免长时间阻塞请求。
- **批量操作性能**：快照批量删除操作应考虑大数据量处理，建议使用异步任务和进度跟踪。
- **交易日历查询优化**：频繁的交易日查询应建立适当的索引，提高查询效率。

## 故障排除指南
- 认证失败
  - 缺少令牌：401，提示 Missing authentication token。
  - 令牌无效或过期：401，提示 Invalid or expired token。
  - 令牌在黑名单：401，提示 Token has been revoked。
  - 账户锁定：403，包含 locked_until 时间戳。
- 权限不足
  - 非管理员访问管理员接口：403，提示 Admin privileges required。
  - viewer 查看他人订阅：403，提示 Permission denied。
- 业务校验失败
  - 非交易日：422，提示 Non-trading day。
  - 可用资金不足：422，提示 Insufficient cash。
  - 可用份额不足：422，提示 Insufficient shares。
  - 产品/组合不存在：404，提示 Not found。
  - **新增** 净值价格不匹配：422，提示 PRICE_NAV_MISMATCH - 提供的价格与基金净值不一致，请检查价格准确性或使用系统自动获取的净值。
- 任务执行异常
  - 任务失败：500，包含错误信息；日志中记录失败详情。
- **OpenAPI规范问题**
  - 导出失败：检查后端服务是否运行，网络连接是否正常。
  - Apifox导入失败：确认openapi.json格式正确，版本兼容。
- **通知系统问题**
  - 通知查询为空：检查投资者代码是否正确，确认通知是否存在。
  - 标记已读失败：验证通知ID有效性，检查用户权限。
- **净值覆盖率验证问题**
  - 覆盖率计算异常：检查投资组合持仓数据是否完整，确认日期范围内的净值数据是否存在。
  - 端点响应缓慢：检查数据库查询性能，考虑添加适当的索引和优化查询逻辑。
- **交易日历查询问题**
  - next/prev端点返回空值：检查输入日期格式是否正确，确认数据库中是否有对应的交易日数据。
  - is-open端点判断异常：验证日期格式，检查时区设置是否正确。
- **批量操作问题**
  - 批量删除失败：检查dry_run模式是否正确配置，确认目标快照存在且具有删除权限。
  - 批量操作超时：对于大量数据操作，建议使用异步处理和进度跟踪。

**更新** 新增PRICE_NAV_MISMATCH错误码说明：当处理场外基金交易确认时，如果客户端提供的价格与系统获取的基金净值不一致，将返回此错误码。建议客户端在遇到此错误时，重新获取最新的基金净值或允许系统自动确定确认价格。

**章节来源**
- [backend/app/dependencies.py:58-111](file://backend/app/dependencies.py#L58-L111)
- [backend/app/routers/trades.py:298-336](file://backend/app/routers/trades.py#L298-L336)
- [backend/app/routers/subscriptions.py:121-140](file://backend/app/routers/subscriptions.py#L121-L140)
- [backend/app/routers/tasks.py:259-267](file://backend/app/routers/tasks.py#L259-L267)
- [backend/export_openapi.py:21-30](file://backend/export_openapi.py#L21-L30)

## 结论
本 API 文档覆盖 InvestRing 后端主要业务模块，明确了认证与权限、数据模型、关键流程与错误处理。新增的OpenAPI规范管理功能提供了完整的API文档自动化解决方案，支持Apifox等工具导入，便于团队协作和API文档维护。**特别重要的是，OpenAPI规范的增强使得投资组合相关的API端点获得了更完整的schema定义，特别是NavHistoryRecord模型的使用，为前端开发提供了更准确的数据结构指导。** 同时，新增的PRICE_NAV_MISMATCH错误码增强了场外基金交易的错误处理能力，提高了系统的健壮性和用户体验。新增的完整通知系统API端点进一步丰富了系统功能，支持管理员进行通知管理和用户通知服务。**特别重要的是，新增的nav-coverage端点为投资组合净值数据完整性验证提供了专业化工具，帮助管理员及时发现和解决数据缺失问题，确保投资分析的准确性和可靠性。** 本次更新新增的交易日历查询功能、快照批量管理能力、投资组合聚合指标和持仓可用份额查询等功能，进一步提升了系统的完整性和实用性。建议在生产环境中补充速率限制、审计日志与监控告警，并持续完善版本演进策略与向后兼容保障。

## 附录
- 认证流程时序图

```mermaid
sequenceDiagram
participant Client as "客户端"
participant Auth as "认证路由"
participant DB as "数据库"
participant Sec as "安全工具"
Client->>Auth : POST /api/auth/login
Auth->>DB : 查询投资人
DB-->>Auth : 返回投资人
Auth->>Sec : 校验密码
Sec-->>Auth : 校验结果
Auth->>Sec : 生成JWT
Sec-->>Auth : 返回token
Auth-->>Client : 返回token与过期时间
Client->>Auth : POST /api/auth/logout
Auth->>Sec : 加入黑名单
Sec-->>Auth : 成功
Auth-->>Client : 返回登出成功
```

**图表来源**
- [backend/app/routers/auth.py:29-119](file://backend/app/routers/auth.py#L29-L119)
- [backend/app/utils/security.py:29-46](file://backend/app/utils/security.py#L29-L46)

- 交易确认流程时序图

```mermaid
sequenceDiagram
participant Client as "客户端"
participant Trades as "交易路由"
participant DB as "数据库"
participant Prod as "产品模型"
participant Cal as "交易日历"
participant Price as "净值记录"
participant Err as "错误处理"
Client->>Trades : POST /api/trades
Trades->>Cal : 校验交易日
Cal-->>Trades : 交易日
Trades->>DB : 查询组合/产品
DB-->>Trades : 返回
Trades->>Trades : 可用资金/份额校验
Trades->>DB : 创建待确认交易
DB-->>Trades : 返回
Client->>Trades : POST /api/trades/{id}/confirm
Trades->>Prod : 获取产品确认天数
Prod-->>Trades : 返回
Trades->>Price : 获取净值净值型
Price-->>Trades : 返回净值或为空
alt 净值价格不匹配
Trades->>Err : 返回PRICE_NAV_MISMATCH错误
Err-->>Client : 返回错误信息
else 价格匹配
Trades->>DB : 更新交易状态与确认日期
DB-->>Trades : 返回
Trades-->>Client : 返回确认结果
end
```

**图表来源**
- [backend/app/routers/trades.py:292-504](file://backend/app/routers/trades.py#L292-L504)

- 快照生成流程时序图

```mermaid
sequenceDiagram
participant Client as "客户端"
participant Tasks as "任务路由"
participant Snap as "快照路由"
participant DB as "数据库"
participant Port as "组合"
participant Cal as "交易日历"
Client->>Tasks : POST /api/system/tasks/nav_sync/run
Tasks->>DB : 查询产品并同步净值
DB-->>Tasks : 返回同步结果
Tasks->>Snap : 触发当日快照生成
Snap->>DB : 查询组合
DB-->>Snap : 返回
Snap->>Cal : 校验交易日
Cal-->>Snap : 交易日
Snap->>DB : 生成快照
DB-->>Snap : 返回
Snap-->>Client : 返回生成结果
```

**图表来源**
- [backend/app/routers/tasks.py:112-237](file://backend/app/routers/tasks.py#L112-L237)
- [backend/app/routers/snapshots.py:28-55](file://backend/app/routers/snapshots.py#L28-L55)

- **OpenAPI规范管理流程图**

```mermaid
flowchart TD
A["后端服务启动"] --> B["FastAPI生成OpenAPI规范"]
B --> C["export_openapi.py导出规范"]
C --> D["生成openapi.json文件"]
D --> E["Apifox导入规范"]
E --> F["API文档管理"]
F --> G["团队协作"]
G --> H["版本控制"]
H --> I["CI/CD集成"]
```

**图表来源**
- [backend/export_openapi.py:1-46](file://backend/export_openapi.py#L1-L46)
- [backend/openapi.json:1-200](file://backend/openapi.json#L1-L200)

- **份额变动事件字段重命名说明**

```mermaid
flowchart LR
A["数据库设计文档<br/>ex_date字段"] --> B["初始化脚本<br/>ex_date索引"]
C["后端模型<br/>event_date字段"] --> D["后端Schema<br/>event_date字段"]
E["前端类型定义<br/>event_date字段"] --> F["OpenAPI规范<br/>event_date字段"]
B -.->|字段重命名| A
D -.->|向后兼容| C
F -.->|API兼容性| E
```

**图表来源**
- [Docs/init_data.sql:268](file://Docs/init_data.sql#L268)
- [backend/app/models/share_change_event.py:13](file://backend/app/models/share_change_event.py#L13)
- [backend/app/schemas/share_change_event.py:9](file://backend/app/schemas/share_change_event.py#L9)
- [frontend/src/types/share-change-event.ts:7](file://frontend/src/types/share-change-event.ts#L7)
- [backend/openapi.json:5911](file://backend/openapi.json#L5911)

- **新增错误码说明**

```mermaid
flowchart TD
A["交易确认请求"] --> B{价格验证}
B --> |价格匹配| C["正常确认流程"]
B --> |价格不匹配| D["PRICE_NAV_MISMATCH错误"]
D --> E["返回错误信息"]
E --> F["客户端处理"]
F --> G["重新获取净值"]
F --> H["使用系统净值"]
G --> I["重试确认"]
H --> I
I --> C
```

**图表来源**
- [backend/app/routers/trades.py:417-504](file://backend/app/routers/trades.py#L417-L504)

- **通知系统API流程图**

```mermaid
flowchart TD
A["管理员操作"] --> B["查询通知列表"]
A --> C["标记单条通知已读"]
A --> D["批量标记已读"]
B --> E["按条件筛选<br/>investor_code/read_status/time_range"]
C --> F["更新通知状态"]
D --> G["批量更新状态"]
E --> H["返回分页结果"]
F --> I["返回操作结果"]
G --> I
```

**图表来源**
- [backend/app/routers/notifications.py:1-200](file://backend/app/routers/notifications.py#L1-L200)

- **净值覆盖率验证流程图**

```mermaid
flowchart TD
A["客户端请求"] --> B["GET /api/market-data/portfolios/{portfolio_code}/nav-coverage"]
B --> C["解析查询参数<br/>start_date, end_date"]
C --> D["查询组合持仓"]
D --> E["遍历持仓产品"]
E --> F["检查每个产品在日期范围内的净值数据"]
F --> G["计算覆盖率统计"]
G --> H["生成缺失日期列表"]
H --> I["返回覆盖率分析报告"]
I --> J["客户端处理结果"]
```

**图表来源**
- [backend/app/routers/market_data.py:1944-2000](file://backend/app/routers/market_data.py#L1944-L2000)

- **投资组合净值历史数据结构**

```mermaid
flowchart TD
A["NavHistoryRecord模型"] --> B["date字段<br/>净值日期"]
A --> C["nav_value字段<br/>单位净值"]
A --> D["total_value字段<br/>组合总值"]
A --> E["total_shares字段<br/>总份额"]
B --> F["标准化日期格式"]
C --> G["数值精度控制"]
D --> H["总值计算逻辑"]
E --> I["份额汇总算法"]
```

**图表来源**
- [backend/app/routers/portfolios.py:159-191](file://backend/app/routers/portfolios.py#L159-L191)
- [backend/openapi.json:1-200](file://backend/openapi.json#L1-L200)

- **交易日历查询流程图**

```mermaid
flowchart TD
A["客户端请求"] --> B{"查询类型"}
B --> |下一个交易日| C["GET /api/trading-calendar/next"]
B --> |上一个交易日| D["GET /api/trading-calendar/prev"]
B --> |交易状态检查| E["GET /api/trading-calendar/is-open"]
C --> F["解析from_date参数"]
D --> G["解析to_date参数"]
E --> H["解析date参数"]
F --> I["查询数据库获取下一个交易日"]
G --> J["查询数据库获取上一个交易日"]
H --> K["检查指定日期是否为交易日"]
I --> L["返回交易日信息"]
J --> L
K --> L
```

**图表来源**
- [backend/app/routers/trading_calendar.py:1547-1588](file://backend/app/routers/trading_calendar.py#L1547-L1588)

- **快照批量删除流程图**

```mermaid
flowchart TD
A["客户端请求"] --> B["DELETE /api/v1/snapshots/batch"]
B --> C["解析请求体<br/>portfolio_codes, date_range, dry_run"]
C --> D{"dry_run模式?"}
D --> |是| E["预检查快照存在性"]
D --> |否| F["执行实际删除操作"]
E --> G["返回预检查结果"]
F --> H["批量删除快照"]
H --> I["返回删除结果"]
G --> J["客户端处理预检查结果"]
I --> J
```

**图表来源**
- [backend/app/routers/snapshots.py:160-200](file://backend/app/routers/snapshots.py#L160-L200)

- **投资组合聚合指标流程图**

```mermaid
flowchart TD
A["客户端请求"] --> B["GET /api/portfolios/{code}/aggregation"]
B --> C["解析查询参数<br/>start_date, end_date"]
C --> D["查询组合历史数据"]
D --> E["计算total_value<br/>组合总值"]
D --> F["计算cumulative_return<br/>累计收益率"]
D --> G["统计investor_count<br/>投资者数量"]
E --> H["生成聚合结果"]
F --> H
G --> H
H --> I["返回聚合指标"]
```

**图表来源**
- [backend/app/routers/portfolios.py:278-320](file://backend/app/routers/portfolios.py#L278-L320)

- **持仓可用份额查询流程图**

```mermaid
flowchart TD
A["客户端请求"] --> B["GET /api/positions/portfolio/{portfolio_code}/product/{product_code}/available-shares"]
B --> C["解析路径参数<br/>portfolio_code, product_code"]
C --> D["解析查询参数<br/>market可选"]
D --> E["查询投资组合持仓"]
E --> F["过滤指定产品持仓"]
F --> G["计算可用份额"]
G --> H["返回可用份额信息"]
```

**图表来源**
- [backend/app/routers/positions.py:296-316](file://backend/app/routers/positions.py#L296-L316)