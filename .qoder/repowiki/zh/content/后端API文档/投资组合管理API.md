# 投资组合管理API

<cite>
**本文引用的文件**
- [backend/app/routers/portfolios.py](file://backend/app/routers/portfolios.py)
- [backend/app/schemas/portfolio.py](file://backend/app/schemas/portfolio.py)
- [backend/app/models/portfolio.py](file://backend/app/models/portfolio.py)
- [backend/app/models/portfolio_position.py](file://backend/app/models/portfolio_position.py)
- [backend/app/models/portfolio_value_snapshot.py](file://backend/app/models/portfolio_value_snapshot.py)
- [backend/app/models/subscription.py](file://backend/app/models/subscription.py)
- [backend/app/models/trade.py](file://backend/app/models/trade.py)
- [backend/app/models/investor.py](file://backend/app/models/investor.py)
- [backend/app/dependencies.py](file://backend/app/dependencies.py)
- [backend/app/schemas/position.py](file://backend/app/schemas/position.py)
- [backend/app/models/product.py](file://backend/app/models/product.py)
- [backend/app/models/platform.py](file://backend/app/models/platform.py)
- [Docs/02-数据库设计.md](file://Docs/02-数据库设计.md)
- [Docs/03-业务流程设计.md](file://Docs/03-业务流程设计.md)
</cite>

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构总览](#架构总览)
5. [详细组件分析](#详细组件分析)
6. [依赖分析](#依赖分析)
7. [性能考虑](#性能考虑)
8. [故障排查指南](#故障排查指南)
9. [结论](#结论)
10. [附录](#附录)

## 简介
本文件为 InvestRing 投资组合管理模块的详细API文档，覆盖以下主题：
- 投资组合的CRUD操作与状态管理（草稿/启用/关闭）
- 组合配置更新、成员管理（通过相关联的订阅与交易）
- 高级查询：列表分页、条件筛选、净值/收益/现金流统计
- 权限控制：普通用户与管理员权限差异
- 请求/响应格式与典型示例
- 数据验证规则与组合约束条件

## 项目结构
投资组合管理API位于后端FastAPI路由模块中，配合Pydantic模型与SQLAlchemy ORM模型实现数据访问与业务逻辑。

```mermaid
graph TB
subgraph "后端服务"
R["路由模块<br/>portfolios.py"]
S["Schema模型<br/>portfolio.py"]
M["ORM模型<br/>portfolio.py"]
D["依赖注入与鉴权<br/>dependencies.py"]
end
subgraph "关联模型"
P["portfolio_position.py"]
V["portfolio_value_snapshot.py"]
T["trade.py"]
SUB["subscription.py"]
INV["investor.py"]
PRD["product.py"]
PLAT["platform.py"]
end
R --> S
R --> M
R --> D
R --> P
R --> V
R --> T
R --> SUB
R --> INV
R --> PRD
R --> PLAT
```

图表来源
- [backend/app/routers/portfolios.py:1-276](file://backend/app/routers/portfolios.py#L1-L276)
- [backend/app/schemas/portfolio.py:1-30](file://backend/app/schemas/portfolio.py#L1-L30)
- [backend/app/models/portfolio.py:1-16](file://backend/app/models/portfolio.py#L1-L16)
- [backend/app/dependencies.py:1-146](file://backend/app/dependencies.py#L1-L146)

章节来源
- [backend/app/routers/portfolios.py:1-276](file://backend/app/routers/portfolios.py#L1-L276)
- [backend/app/schemas/portfolio.py:1-30](file://backend/app/schemas/portfolio.py#L1-L30)
- [backend/app/models/portfolio.py:1-16](file://backend/app/models/portfolio.py#L1-L16)
- [backend/app/dependencies.py:1-146](file://backend/app/dependencies.py#L1-L146)

## 核心组件
- 路由器：提供投资组合的CRUD、状态切换、统计查询等接口
- Schema模型：定义请求/响应的数据结构
- ORM模型：映射数据库表结构与约束
- 依赖注入：鉴权与权限校验（普通用户/管理员）

章节来源
- [backend/app/routers/portfolios.py:1-276](file://backend/app/routers/portfolios.py#L1-L276)
- [backend/app/schemas/portfolio.py:1-30](file://backend/app/schemas/portfolio.py#L1-L30)
- [backend/app/models/portfolio.py:1-16](file://backend/app/models/portfolio.py#L1-L16)
- [backend/app/dependencies.py:114-129](file://backend/app/dependencies.py#L114-L129)

## 架构总览
投资组合管理API遵循REST风格，使用Bearer Token进行鉴权；管理员具备组合创建、更新、状态切换等管理能力，普通用户可查询组合信息与统计数据。

```mermaid
sequenceDiagram
participant 客户端 as "客户端"
participant 路由 as "portfolios.py"
participant 依赖 as "dependencies.py"
participant DB as "数据库"
客户端->>路由 : "GET /portfolios?status=active&page=1&page_size=20"
路由->>依赖 : "get_current_user()"
依赖-->>路由 : "Investor对象"
路由->>DB : "查询组合列表(分页)"
DB-->>路由 : "结果集"
路由-->>客户端 : "JSON 列表+分页信息"
客户端->>路由 : "POST /portfolios (管理员)"
路由->>依赖 : "get_current_admin()"
依赖-->>路由 : "Investor(角色=admin)"
路由->>DB : "插入新组合(默认状态draft)"
DB-->>路由 : "新记录"
路由-->>客户端 : "PortfolioResponse"
```

图表来源
- [backend/app/routers/portfolios.py:18-36](file://backend/app/routers/portfolios.py#L18-L36)
- [backend/app/routers/portfolios.py:39-58](file://backend/app/routers/portfolios.py#L39-L58)
- [backend/app/dependencies.py:49-129](file://backend/app/dependencies.py#L49-L129)

## 详细组件分析

### 1. 投资组合列表查询
- 方法与路径
  - GET /portfolios
- 查询参数
  - status: 状态过滤（draft/active/closed）
  - page: 页码（默认1）
  - page_size: 每页条数（默认20）
- 认证与权限
  - 需要登录（普通用户）
- 响应
  - items: 组合列表
  - total: 总数
  - page/page_size: 分页信息
- 示例
  - 请求: GET /portfolios?status=active&page=1&page_size=20
  - 响应: 包含items与分页元数据的对象

章节来源
- [backend/app/routers/portfolios.py:18-36](file://backend/app/routers/portfolios.py#L18-L36)

### 2. 创建投资组合
- 方法与路径
  - POST /portfolios
- 请求体
  - code: 组合编码（唯一）
  - name: 组合名称
  - description: 描述（可选）
- 认证与权限
  - 需要管理员权限
- 响应
  - PortfolioResponse（默认状态为draft）
- 错误
  - 若code已存在，返回400
- 示例
  - 请求: POST /portfolios
  - 响应: PortfolioResponse（包含默认状态draft）

章节来源
- [backend/app/routers/portfolios.py:39-58](file://backend/app/routers/portfolios.py#L39-L58)
- [backend/app/schemas/portfolio.py:12-13](file://backend/app/schemas/portfolio.py#L12-L13)
- [backend/app/models/portfolio.py:8-11](file://backend/app/models/portfolio.py#L8-L11)

### 3. 查询单个投资组合
- 方法与路径
  - GET /portfolios/{code}
- 路径参数
  - code: 组合编码
- 认证与权限
  - 需要登录（普通用户）
- 响应
  - PortfolioResponse
- 错误
  - 未找到返回404

章节来源
- [backend/app/routers/portfolios.py:61-70](file://backend/app/routers/portfolios.py#L61-L70)
- [backend/app/schemas/portfolio.py:21-29](file://backend/app/schemas/portfolio.py#L21-L29)

### 4. 更新投资组合
- 方法与路径
  - PUT /portfolios/{code}
- 路径参数
  - code: 组合编码
- 请求体
  - name/description（可选）
- 认证与权限
  - 需要管理员权限
- 响应
  - PortfolioResponse（更新后的记录）
- 错误
  - 未找到返回404

章节来源
- [backend/app/routers/portfolios.py:73-89](file://backend/app/routers/portfolios.py#L73-L89)
- [backend/app/schemas/portfolio.py:16-18](file://backend/app/schemas/portfolio.py#L16-L18)

### 5. 关闭投资组合
- 方法与路径
  - POST /portfolios/{code}/close
- 路径参数
  - code: 组合编码
- 认证与权限
  - 需要管理员权限
- 业务规则
  - 仅当组合状态为非closed时可关闭
  - 若存在待处理的订阅或交易（status=pending），则拒绝关闭
  - 关闭后设置closed_at为当前UTC时间
- 响应
  - {"message": "Portfolio closed successfully"}
- 错误
  - 组合不存在：404
  - 已关闭：422（PORTFOLIO_ALREADY_CLOSED）
  - 存在待处理交易：422（PENDING_TRANSACTIONS_EXIST）

章节来源
- [backend/app/routers/portfolios.py:92-131](file://backend/app/routers/portfolios.py#L92-L131)
- [backend/app/models/subscription.py](file://backend/app/models/subscription.py#L17)
- [backend/app/models/trade.py](file://backend/app/models/trade.py#L21)

### 6. 重新激活投资组合
- 方法与路径
  - POST /portfolios/{code}/reactivate
- 路径参数
  - code: 组合编码
- 认证与权限
  - 需要管理员权限
- 业务规则
  - 仅当组合状态为closed时可重新激活
  - 激活后重置closed_at为None
- 响应
  - {"message": "Portfolio reactivated successfully"}
- 错误
  - 组合不存在：404
  - 非closed状态：422（PORTFOLIO_NOT_CLOSED）

章节来源
- [backend/app/routers/portfolios.py:134-156](file://backend/app/routers/portfolios.py#L134-L156)

### 7. 净值历史查询
- 方法与路径
  - GET /portfolios/{code}/nav-history
- 查询参数
  - start_date: 开始日期（可选）
  - end_date: 结束日期（可选）
- 认证与权限
  - 需要登录（普通用户）
- 响应
  - portfolio_code: 组合编码
  - data: 时间序列数组，元素包含date、unit_price、total_value、total_shares
- 错误
  - 未找到返回404

章节来源
- [backend/app/routers/portfolios.py:159-191](file://backend/app/routers/portfolios.py#L159-L191)
- [backend/app/models/portfolio_value_snapshot.py:8-15](file://backend/app/models/portfolio_value_snapshot.py#L8-L15)

### 8. 组合收益统计
- 方法与路径
  - GET /portfolios/{code}/returns
- 认证与权限
  - 需要登录（普通用户）
- 响应
  - portfolio_code: 组合编码
  - cumulative_return: 累计收益率（百分比）
  - annualized_return: 年化收益率（百分比，若持有天数>0）
  - initial_nav/current_nav: 初始与最新单位净值
  - holding_days: 持有天数
- 特殊情况
  - 若无快照，返回null对应字段

章节来源
- [backend/app/routers/portfolios.py:194-241](file://backend/app/routers/portfolios.py#L194-L241)

### 9. 组合现金流统计
- 方法与路径
  - GET /portfolios/{code}/cash-flow
- 认证与权限
  - 需要登录（普通用户）
- 响应
  - portfolio_code: 组合编码
  - total_inflow: 确认申购总金额
  - total_outflow: 确认赎回总金额
  - net_inflow: 净流入（合计差额）
- 错误
  - 未找到返回404

章节来源
- [backend/app/routers/portfolios.py:244-275](file://backend/app/routers/portfolios.py#L244-L275)

### 10. 投资组合数据模型与约束
- 模型字段（Portfolio）
  - code: 主键（唯一）
  - name: 名称
  - description: 描述
  - status: 状态（draft/active/closed）
  - started_at/closed_at: 生命周期时间戳
  - created_at/updated_at: 自动维护
- 约束与规则
  - status默认draft
  - started_at在首次确认申购时设置
  - 关闭前需检查待处理交易（订阅/交易）
- 外键与RESTRICT策略
  - portfolio与portfolio_position/portfolio_value_snapshot/subscription等关联采用RESTRICT，禁止直接删除

章节来源
- [backend/app/models/portfolio.py:5-15](file://backend/app/models/portfolio.py#L5-L15)
- [Docs/02-数据库设计.md:32-62](file://Docs/02-数据库设计.md#L32-L62)
- [Docs/02-数据库设计.md:599-621](file://Docs/02-数据库设计.md#L599-L621)

### 11. 权限与鉴权
- 普通用户（get_current_user）
  - 需要有效Token，Token未失效且账户未锁定
- 管理员（get_current_admin）
  - 在普通用户基础上要求角色为admin
- 适用范围
  - 列表查询：普通用户
  - 创建/更新/状态切换：管理员
  - 统计查询：普通用户

章节来源
- [backend/app/dependencies.py:49-129](file://backend/app/dependencies.py#L49-L129)

### 12. 组合成员与相关实体
- 投资者（Investor）
  - 角色role支持admin/viewer
- 订阅（Subscription）
  - 关联portfolio与investor，记录申购/赎回申请与确认
- 交易（Trade）
  - 记录买入/卖出交易及确认状态
- 组合持仓（PortfolioPosition）
  - 记录每日持仓快照，支持按产品与市场维度
- 产品（Product）与平台（Platform）
  - 产品定义与数据源，平台定义交易渠道

章节来源
- [backend/app/models/investor.py:5-16](file://backend/app/models/investor.py#L5-L16)
- [backend/app/models/subscription.py:5-20](file://backend/app/models/subscription.py#L5-L20)
- [backend/app/models/trade.py:5-31](file://backend/app/models/trade.py#L5-L31)
- [backend/app/models/portfolio_position.py:5-33](file://backend/app/models/portfolio_position.py#L5-L33)
- [backend/app/models/product.py:5-21](file://backend/app/models/product.py#L5-L21)
- [backend/app/models/platform.py:5-11](file://backend/app/models/platform.py#L5-L11)

## 依赖分析
- 路由对依赖模块的使用
  - get_current_user：用于普通用户鉴权
  - get_current_admin：用于管理员鉴权
- 路由对模型的使用
  - Portfolio：CRUD与状态管理
  - PortfolioValueSnapshot：净值历史与收益计算
  - Subscription/Trade：关闭前待处理检查
- 外键与约束
  - portfolio与多个子表采用RESTRICT，避免误删

```mermaid
graph LR
PORT["Portfolio"] --> SNAP["PortfolioValueSnapshot"]
PORT --> SUB["Subscription"]
PORT --> TRADE["Trade"]
PORT --> POS["PortfolioPosition"]
POS --> PRD["Product"]
POS --> PLAT["Platform"]
```

图表来源
- [backend/app/models/portfolio.py:5-15](file://backend/app/models/portfolio.py#L5-L15)
- [backend/app/models/portfolio_value_snapshot.py:5-15](file://backend/app/models/portfolio_value_snapshot.py#L5-L15)
- [backend/app/models/subscription.py:5-20](file://backend/app/models/subscription.py#L5-L20)
- [backend/app/models/trade.py:5-31](file://backend/app/models/trade.py#L5-L31)
- [backend/app/models/portfolio_position.py:5-33](file://backend/app/models/portfolio_position.py#L5-L33)
- [backend/app/models/product.py:5-21](file://backend/app/models/product.py#L5-L21)
- [backend/app/models/platform.py:5-11](file://backend/app/models/platform.py#L5-L11)

章节来源
- [backend/app/routers/portfolios.py:1-276](file://backend/app/routers/portfolios.py#L1-L276)
- [backend/app/dependencies.py:1-146](file://backend/app/dependencies.py#L1-L146)

## 性能考虑
- 分页查询：列表接口支持page与page_size，建议前端按需分页，避免一次性拉取过多数据
- 状态过滤：通过status参数快速筛选目标组合集合
- 统计查询：净值历史与收益计算基于快照表，建议在业务侧缓存热点组合的近期数据以降低查询压力
- 关闭前检查：关闭接口会扫描待处理交易，建议在业务流程中提前清理pending状态

## 故障排查指南
- 401 未授权
  - 缺少Token或Token无效/过期；检查鉴权头与Token黑名单
- 403 禁止访问
  - 非管理员尝试创建/更新/状态切换
- 404 未找到
  - 组合编码不存在
- 422 业务校验失败
  - 关闭时组合已关闭/存在待处理交易
  - 重新激活时组合非closed状态
- 400 重复
  - 创建时组合code已存在

章节来源
- [backend/app/routers/portfolios.py:45-47](file://backend/app/routers/portfolios.py#L45-L47)
- [backend/app/routers/portfolios.py:102-126](file://backend/app/routers/portfolios.py#L102-L126)
- [backend/app/routers/portfolios.py:144-151](file://backend/app/routers/portfolios.py#L144-L151)
- [backend/app/dependencies.py:58-101](file://backend/app/dependencies.py#L58-L101)

## 结论
本API提供了完备的投资组合管理能力：从基础CRUD到状态全生命周期管理，再到净值、收益与现金流的统计查询。通过严格的权限控制与业务校验，保障了组合数据的一致性与安全性。建议在前端集成时结合分页与状态过滤，提升用户体验；在后端优化热点数据缓存与批量查询，提升响应性能。

## 附录

### A. 接口一览与权限对照
- GET /portfolios：普通用户
- POST /portfolios：管理员
- GET /portfolios/{code}：普通用户
- PUT /portfolios/{code}：管理员
- POST /portfolios/{code}/close：管理员
- POST /portfolios/{code}/reactivate：管理员
- GET /portfolios/{code}/nav-history：普通用户
- GET /portfolios/{code}/returns：普通用户
- GET /portfolios/{code}/cash-flow：普通用户

章节来源
- [backend/app/routers/portfolios.py:18-275](file://backend/app/routers/portfolios.py#L18-L275)
- [backend/app/dependencies.py:49-129](file://backend/app/dependencies.py#L49-L129)

### B. 数据验证与约束要点
- 组合code唯一，创建时若重复返回400
- 关闭前必须清理所有pending的订阅与交易
- 状态切换仅在特定状态下允许（已关闭才能重新激活，非closed才能关闭）
- 快照表与持仓表采用唯一约束，避免重复快照

章节来源
- [backend/app/routers/portfolios.py:45-47](file://backend/app/routers/portfolios.py#L45-L47)
- [backend/app/routers/portfolios.py:102-126](file://backend/app/routers/portfolios.py#L102-L126)
- [backend/app/routers/portfolios.py:144-151](file://backend/app/routers/portfolios.py#L144-L151)
- [backend/app/models/portfolio_value_snapshot.py:17-19](file://backend/app/models/portfolio_value_snapshot.py#L17-L19)
- [backend/app/models/portfolio_position.py:23-33](file://backend/app/models/portfolio_position.py#L23-L33)