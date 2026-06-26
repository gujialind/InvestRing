# API 客户端设计

<cite>
**本文档引用的文件**
- [frontend/src/lib/api/index.ts](file://frontend/src/lib/api/index.ts)
- [frontend/src/lib/api/client.ts](file://frontend/src/lib/api/client.ts)
- [frontend/src/lib/api/auth.ts](file://frontend/src/lib/api/auth.ts)
- [frontend/src/lib/api/investor.ts](file://frontend/src/lib/api/investor.ts)
- [frontend/src/lib/api/portfolio.ts](file://frontend/src/lib/api/portfolio.ts)
- [frontend/src/lib/api/product.ts](file://frontend/src/lib/api/product.ts)
- [frontend/src/lib/api/platform.ts](file://frontend/src/lib/api/platform.ts)
- [frontend/src/lib/api/trade.ts](file://frontend/src/lib/api/trade.ts)
- [frontend/src/lib/api/position.ts](file://frontend/src/lib/api/position.ts)
- [frontend/src/lib/api/subscription.ts](file://frontend/src/lib/api/subscription.ts)
- [frontend/src/lib/api/snapshot.ts](file://frontend/src/lib/api/snapshot.ts)
- [frontend/src/lib/api/share-change-event.ts](file://frontend/src/lib/api/share-change-event.ts)
- [frontend/src/lib/api/notification.ts](file://frontend/src/lib/api/notification.ts)
- [frontend/src/lib/api/log.ts](file://frontend/src/lib/api/log.ts)
- [frontend/src/lib/api/system.ts](file://frontend/src/lib/api/system.ts)
- [frontend/src/lib/api/task.ts](file://frontend/src/lib/api/task.ts)
- [frontend/src/stores/authStore.ts](file://frontend/src/stores/authStore.ts)
- [frontend/src/hooks/useAuth.ts](file://frontend/src/hooks/useAuth.ts)
- [frontend/src/types/auth.ts](file://frontend/src/types/auth.ts)
- [frontend/src/types/common.ts](file://frontend/src/types/common.ts)
- [frontend/src/stores/uiStore.ts](file://frontend/src/stores/uiStore.ts)
- [frontend/src/app/providers.tsx](file://frontend/src/app/providers.tsx)
- [frontend/src/middleware.ts](file://frontend/src/middleware.ts)
- [backend/app/main.py](file://backend/app/main.py)
- [backend/app/routers/auth.py](file://backend/app/routers/auth.py)
- [backend/app/config.py](file://backend/app/config.py)
- [frontend/package.json](file://frontend/package.json)
- [backend/requirements.txt](file://backend/requirements.txt)
</cite>

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

InvestRing 项目采用前后端分离架构，前端使用 Next.js + TypeScript + React Query 构建，后端使用 FastAPI 提供 RESTful API 服务。本设计文档专注于前端 API 客户端的设计与实现，涵盖 HTTP 客户端封装、请求/响应拦截器、错误处理机制、认证令牌管理、重试策略、超时配置、并发控制以及最佳实践等内容。

**重要变更**：项目已从单一 monolithic API 模块重构为模块化的业务域驱动架构。新的架构将 API 功能按业务领域进行模块化组织，提高了代码的可维护性和可扩展性。

## 项目结构

前端项目采用模块化的业务域驱动架构，API 客户端位于 `src/lib/api/` 目录下，按业务领域划分为独立的模块：

```mermaid
graph TB
subgraph "模块化 API 架构"
AuthAPI["认证模块<br/>src/lib/api/auth.ts"]
InvestorAPI["投资人模块<br/>src/lib/api/investor.ts"]
PortfolioAPI["组合模块<br/>src/lib/api/portfolio.ts"]
ProductAPI["产品模块<br/>src/lib/api/product.ts"]
PlatformAPI["平台模块<br/>src/lib/api/platform.ts"]
TradeAPI["交易模块<br/>src/lib/api/trade.ts"]
PositionAPI["持仓模块<br/>src/lib/api/position.ts"]
SubscriptionAPI["订阅模块<br/>src/lib/api/subscription.ts"]
SnapshotAPI["快照模块<br/>src/lib/api/snapshot.ts"]
ShareEventAPI["份额事件模块<br/>src/lib/api/share-change-event.ts"]
NotificationAPI["通知模块<br/>src/lib/api/notification.ts"]
LogAPI["日志模块<br/>src/lib/api/log.ts"]
SystemAPI["系统模块<br/>src/lib/api/system.ts"]
TaskAPI["任务模块<br/>src/lib/api/task.ts"]
IndexAPI["API 导出入口<br/>src/lib/api/index.ts"]
ClientAPI["HTTP 客户端<br/>src/lib/api/client.ts"]
end
subgraph "状态管理"
AuthStore["认证状态存储<br/>src/stores/authStore.ts"]
UIStore["UI 状态存储<br/>src/stores/uiStore.ts"]
end
subgraph "Hooks"
AuthHook["认证 Hook<br/>src/hooks/useAuth.ts"]
end
subgraph "后端"
FastAPI["FastAPI 应用<br/>backend/app/main.py"]
AuthRouter["认证路由<br/>backend/app/routers/auth.py"]
Config["配置管理<br/>backend/app/config.py"]
end
AuthAPI --> ClientAPI
InvestorAPI --> ClientAPI
PortfolioAPI --> ClientAPI
ProductAPI --> ClientAPI
TradeAPI --> ClientAPI
ClientAPI --> FastAPI
AuthStore --> AuthAPI
AuthHook --> AuthAPI
IndexAPI --> AuthAPI
IndexAPI --> InvestorAPI
IndexAPI --> PortfolioAPI
IndexAPI --> ProductAPI
IndexAPI --> PlatformAPI
IndexAPI --> TradeAPI
IndexAPI --> PositionAPI
IndexAPI --> SubscriptionAPI
IndexAPI --> SnapshotAPI
IndexAPI --> ShareEventAPI
IndexAPI --> NotificationAPI
IndexAPI --> LogAPI
IndexAPI --> SystemAPI
IndexAPI --> TaskAPI
```

**图表来源**
- [frontend/src/lib/api/index.ts:1-100](file://frontend/src/lib/api/index.ts#L1-L100)
- [frontend/src/lib/api/client.ts:1-200](file://frontend/src/lib/api/client.ts#L1-L200)
- [frontend/src/lib/api/auth.ts:1-150](file://frontend/src/lib/api/auth.ts#L1-L150)
- [backend/app/main.py:1-53](file://backend/app/main.py#L1-L53)

**章节来源**
- [frontend/src/lib/api/index.ts:1-100](file://frontend/src/lib/api/index.ts#L1-L100)
- [frontend/src/lib/api/client.ts:1-200](file://frontend/src/lib/api/client.ts#L1-L200)
- [backend/app/main.py:1-53](file://backend/app/main.py#L1-L53)

## 核心组件

### HTTP 客户端实例

项目基于 Axios 创建了统一的 HTTP 客户端实例，配置了基础 URL、请求头和超时时间：

- 基础 URL：从环境变量 `NEXT_PUBLIC_API_URL` 获取，默认为 `/api`
- Content-Type：固定为 `application/json`
- 超时时间：30000ms（30秒）
- 支持请求/响应拦截器链式处理

### 模块化 API 设计

新的架构采用按业务域划分的模块化设计：

**认证模块** (`auth.ts`)：处理用户认证、令牌管理和用户信息
**投资人模块** (`investor.ts`)：管理投资人相关信息
**组合模块** (`portfolio.ts`)：处理投资组合的 CRUD 操作
**产品模块** (`product.ts`)：管理金融产品信息
**平台模块** (`platform.ts`)：处理平台相关功能
**交易模块** (`trade.ts`)：管理交易相关操作
**持仓模块** (`position.ts`)：处理持仓信息
**订阅模块** (`subscription.ts`)：管理订阅相关功能
**快照模块** (`snapshot.ts`)：处理净值快照
**份额事件模块** (`share-change-event.ts`)：管理份额变动事件
**通知模块** (`notification.ts`)：处理系统通知
**日志模块** (`log.ts`)：管理各类日志
**系统模块** (`system.ts`)：系统配置和管理
**任务模块** (`task.ts`)：处理后台任务

### 统一导出接口

通过 `index.ts` 提供统一的 API 访问接口：

```typescript
export * from './client';
export * from './auth';
export * from './investor';
export * from './portfolio';
export * from './product';
export * from './platform';
export * from './trade';
export * from './position';
export * from './subscription';
export * from './snapshot';
export * from './share-change-event';
export * from './notification';
export * from './log';
export * from './system';
export * from './task';
```

**章节来源**
- [frontend/src/lib/api/client.ts:1-200](file://frontend/src/lib/api/client.ts#L1-L200)
- [frontend/src/lib/api/index.ts:1-100](file://frontend/src/lib/api/index.ts#L1-L100)

## 架构概览

```mermaid
sequenceDiagram
participant Client as "客户端应用"
participant API as "模块化 API 客户端"
participant Module as "业务模块"
participant Interceptor as "拦截器"
participant Backend as "后端服务"
Client->>API : 导入模块化 API
API->>Module : 加载特定业务模块
Module->>Interceptor : 进入请求拦截器
Interceptor->>Interceptor : 读取本地 token
Interceptor->>Module : 添加 Authorization 头
Module->>Backend : 发送 HTTP 请求
Backend-->>Module : 返回响应
Module->>API : 处理响应数据
API-->>Client : 返回模块化数据
Note over Client,Backend : 模块化架构流程
```

**图表来源**
- [frontend/src/lib/api/index.ts:1-100](file://frontend/src/lib/api/index.ts#L1-L100)
- [frontend/src/lib/api/client.ts:1-200](file://frontend/src/lib/api/client.ts#L1-L200)

## 详细组件分析

### 模块化架构优势

新的模块化设计带来了以下优势：

1. **职责分离**：每个业务模块负责特定领域的功能
2. **可维护性**：代码结构清晰，易于理解和维护
3. **可扩展性**：新增业务功能只需创建新模块
4. **可测试性**：模块间解耦，便于单元测试
5. **性能优化**：按需加载，减少初始包体积

### 认证令牌管理

#### 令牌存储策略

项目实现了多层令牌存储机制：

```mermaid
flowchart TD
Login["用户登录"] --> StoreToken["存储令牌"]
StoreToken --> LocalStorage["localStorage<br/>持久化存储"]
StoreToken --> Cookie["Cookie<br/>会话存储"]
LocalStorage --> AuthStore["Zustand 状态管理"]
Cookie --> AuthStore
AuthStore --> Request["请求时自动附加"]
Request --> CheckToken{"令牌有效？"}
CheckToken --> |是| SendRequest["发送带令牌的请求"]
CheckToken --> |否| Redirect["跳转登录页"]
Redirect --> ClearStorage["清理本地存储"]
```

**图表来源**
- [frontend/src/stores/authStore.ts:37-51](file://frontend/src/stores/authStore.ts#L37-L51)
- [frontend/src/lib/api/client.ts:150-180](file://frontend/src/lib/api/client.ts#L150-L180)

#### 认证状态管理

使用 Zustand 实现轻量级状态管理：

- 支持持久化存储（localStorage + cookie）
- 提供登录、登出、用户信息设置等操作
- 自动同步 token 和用户状态

**章节来源**
- [frontend/src/stores/authStore.ts:18-71](file://frontend/src/stores/authStore.ts#L18-L71)
- [frontend/src/hooks/useAuth.ts:11-36](file://frontend/src/hooks/useAuth.ts#L11-L36)

### 请求拦截器实现

请求拦截器的核心功能包括：

1. **环境检测**：仅在浏览器环境中读取 token
2. **令牌注入**：自动为每个请求添加 Authorization 头
3. **错误处理**：拦截请求阶段的错误并返回

```mermaid
flowchart TD
Start["请求发起"] --> EnvCheck{"是否浏览器环境？"}
EnvCheck --> |否| Continue["直接发送请求"]
EnvCheck --> |是| ReadToken["读取 localStorage 中的 token"]
ReadToken --> HasToken{"是否存在 token？"}
HasToken --> |否| Continue
HasToken --> |是| AddHeader["添加 Authorization 头"]
AddHeader --> Continue
Continue --> End["请求发送"]
```

**图表来源**
- [frontend/src/lib/api/client.ts:150-180](file://frontend/src/lib/api/client.ts#L150-L180)

**章节来源**
- [frontend/src/lib/api/client.ts:150-180](file://frontend/src/lib/api/client.ts#L150-L180)

### 响应拦截器与错误处理

响应拦截器实现了统一的错误处理策略：

```mermaid
flowchart TD
Response["收到响应"] --> StatusCheck{"状态码检查"}
StatusCheck --> |2xx| Success["正常响应"]
StatusCheck --> |401| Unauthorized["401 未授权"]
StatusCheck --> |其他错误| ErrorHandler["统一错误处理"]
Unauthorized --> ClearToken["清理本地 token"]
ClearToken --> Redirect["跳转登录页"]
ErrorHandler --> ThrowError["抛出 ApiException"]
Success --> ReturnData["返回数据"]
ThrowError --> End["错误传播"]
Redirect --> End
ReturnData --> End
```

**图表来源**
- [frontend/src/lib/api/client.ts:180-200](file://frontend/src/lib/api/client.ts#L180-L200)

#### 异常类设计

`ApiException` 类提供了结构化的错误信息：

- `code`：错误码，来源于后端 API 错误详情
- `status`：HTTP 状态码
- `message`：错误描述信息
- 继承自 Error，保持与 JavaScript 标准异常兼容

**章节来源**
- [frontend/src/lib/api/client.ts:80-120](file://frontend/src/lib/api/client.ts#L80-L120)

### React Query 集成

项目使用 React Query 进行数据缓存和状态管理：

```mermaid
classDiagram
class QueryClient {
+defaultOptions : QueryClientConfig
+getQueryData()
+setQueryData()
+invalidateQueries()
}
class AuthHook {
+useLogin()
+useLogout()
+useCurrentUser()
+useChangePassword()
}
class APIWrapper {
+request()
+handleApiError()
+ApiException
}
QueryClient --> AuthHook : "管理查询状态"
AuthHook --> APIWrapper : "调用 API"
APIWrapper --> QueryClient : "缓存响应数据"
```

**图表来源**
- [frontend/src/app/providers.tsx:8-19](file://frontend/src/app/providers.tsx#L8-L19)
- [frontend/src/hooks/useAuth.ts:11-94](file://frontend/src/hooks/useAuth.ts#L11-L94)

#### 查询配置

- 默认过期时间：30 秒
- 窗口焦点时不自动重新获取
- 失败重试：1 次
- 支持查询键值管理

**章节来源**
- [frontend/src/app/providers.tsx:8-19](file://frontend/src/app/providers.tsx#L8-L19)
- [frontend/src/hooks/useAuth.ts:61-70](file://frontend/src/hooks/useAuth.ts#L61-L70)

### 后端认证流程

后端使用 FastAPI 和 JWT 实现认证：

```mermaid
sequenceDiagram
participant Client as "客户端"
participant AuthRouter as "认证路由"
participant DB as "数据库"
participant Security as "安全工具"
Client->>AuthRouter : POST /api/auth/login
AuthRouter->>DB : 查询用户信息
DB-->>AuthRouter : 用户数据
AuthRouter->>Security : 验证密码
Security-->>AuthRouter : 验证结果
AuthRouter->>Security : 生成 JWT 令牌
Security-->>AuthRouter : 令牌
AuthRouter-->>Client : 返回令牌和用户信息
Note over Client,AuthRouter : 令牌有效期由配置决定
```

**图表来源**
- [backend/app/routers/auth.py:29-95](file://backend/app/routers/auth.py#L29-L95)
- [backend/app/config.py:14-16](file://backend/app/config.py#L14-L16)

**章节来源**
- [backend/app/routers/auth.py:29-95](file://backend/app/routers/auth.py#L29-L95)
- [backend/app/config.py:14-16](file://backend/app/config.py#L14-L16)

## 依赖分析

### 前端依赖

项目的关键依赖包括：

- **axios**：HTTP 客户端库，提供请求/响应拦截器功能
- **@tanstack/react-query**：数据获取和状态管理
- **zustand**：轻量级状态管理库
- **next**：React 框架，提供 SSR 和路由功能

### 后端依赖

后端使用 FastAPI 生态系统：

- **fastapi**：Web 框架
- **uvicorn**：ASGI 服务器
- **sqlalchemy**：ORM 框架
- **python-jose**：JWT 令牌处理
- **passlib**：密码哈希

```mermaid
graph LR
subgraph "前端技术栈"
Axios["axios"]
ReactQuery["@tanstack/react-query"]
Zustand["zustand"]
Next["next"]
end
subgraph "后端技术栈"
FastAPI["fastapi"]
Uvicorn["uvicorn"]
SQLAlchemy["sqlalchemy"]
JWT["python-jose"]
Password["passlib"]
end
Axios --> FastAPI
ReactQuery --> Axios
Zustand --> Next
Next --> FastAPI
```

**图表来源**
- [frontend/package.json:24](file://frontend/package.json#L24)
- [backend/requirements.txt:1](file://backend/requirements.txt#L1)

**章节来源**
- [frontend/package.json:11-38](file://frontend/package.json#L11-L38)
- [backend/requirements.txt:1-19](file://backend/requirements.txt#L1-L19)

## 性能考虑

### 缓存策略

- **查询缓存**：React Query 默认 30 秒过期时间
- **状态持久化**：Zustand 支持本地存储，减少重复请求
- **智能失效**：操作成功后主动失效相关查询

### 并发控制

- **请求去重**：React Query 自动处理重复查询
- **并发限制**：通过查询键值避免不必要的重复请求
- **内存管理**：合理设置过期时间和缓存大小

### 网络优化

- **超时控制**：30 秒全局超时设置
- **错误重试**：默认重试 1 次
- **连接复用**：Axios 实例复用 HTTP 连接

## 故障排除指南

### 常见问题诊断

#### 401 未授权错误

当出现 401 错误时，系统会自动：
1. 清理本地存储的 token
2. 跳转到登录页面
3. 阻止后续请求

#### 网络连接问题

可能的原因包括：
- 后端服务未启动
- CORS 配置不正确
- 网络连接中断
- 代理配置错误

#### 认证状态异常

解决方案：
- 检查 localStorage 中的 token 是否存在
- 验证 token 是否过期
- 确认后端 JWT 密钥配置正确
- 检查用户角色权限

**章节来源**
- [frontend/src/lib/api/client.ts:180-200](file://frontend/src/lib/api/client.ts#L180-L200)
- [frontend/src/stores/authStore.ts:45-51](file://frontend/src/stores/authStore.ts#L45-L51)

### 调试技巧

1. **启用开发模式**：查看详细的错误堆栈信息
2. **检查网络面板**：观察请求和响应详情
3. **验证令牌**：使用 JWT 解码工具检查 token 内容
4. **监控查询状态**：使用 React DevTools 检查查询状态

## 结论

InvestRing 项目的 API 客户端设计体现了现代前端开发的最佳实践：

1. **模块化的业务域驱动架构**：按业务领域划分的清晰模块结构
2. **统一的客户端封装**：基于 Axios 的标准化 HTTP 客户端
3. **完善的拦截器体系**：自动化的认证和错误处理
4. **状态管理集成**：与 React Query 和 Zustand 的无缝集成
5. **可扩展的模块化设计**：支持新业务功能的快速添加
6. **健壮的错误处理**：结构化的异常管理和用户体验

**重大架构升级**：从单一 monolithic API 模块迁移到模块化的业务域驱动架构，显著提升了代码的可维护性、可扩展性和团队协作效率。新的架构为后续的功能扩展和维护奠定了良好的基础，同时保证了系统的稳定性和可维护性。

## 附录

### API 调用最佳实践

1. **使用模块化的 API 客户端**：按业务领域导入相应的 API 模块
2. **合理设置缓存策略**：根据数据变化频率选择合适的缓存时间
3. **错误处理标准化**：统一使用 ApiException 进行错误处理
4. **令牌管理自动化**：利用拦截器自动处理认证头
5. **查询键值规范化**：确保查询参数的顺序和格式一致
6. **模块间解耦**：通过统一的导出接口访问各业务模块

### 错误恢复策略

1. **自动重试**：对于临时性网络错误进行有限次重试
2. **降级处理**：在网络异常时提供基本功能
3. **用户反馈**：及时向用户展示错误信息和恢复选项
4. **日志记录**：记录详细的错误信息用于调试

### 离线支持方案

虽然当前实现主要面向在线场景，但可以考虑以下扩展：
1. **Service Worker**：实现基础的离线缓存
2. **IndexedDB**：持久化存储关键数据
3. **同步队列**：离线操作排队，网络恢复后同步
4. **冲突解决**：处理离线期间的数据冲突