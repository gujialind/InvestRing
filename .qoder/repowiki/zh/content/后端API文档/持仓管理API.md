# 持仓管理API

<cite>
**本文档引用的文件**
- [positions.py](file://backend/app/routers/positions.py)
- [position_service.py](file://backend/app/services/position_service.py)
- [position.py](file://backend/app/schemas/position.py)
- [portfolio_position.py](file://backend/app/models/portfolio_position.py)
- [investor_holding.py](file://backend/app/models/investor_holding.py)
</cite>

## 更新摘要
**所做更改**
- 更新了PositionResponse数据模型，新增product_name、profit_loss、profit_loss_percent字段用于净值型产品收益计算
- 增强了持仓响应数据结构，支持资产类型(asset_type)信息标识
- 完善了净值型产品的收益计算和展示功能
- 优化了持仓查询接口的响应格式和数据完整性

## 目录
- [概述](#概述)
- [认证要求](#认证要求)
- [持仓基础操作](#持仓基础操作)
- [持仓查询接口](#持仓查询接口)
- [持仓调整接口](#持仓调整接口)
- [持仓状态管理](#持仓状态管理)
- [持仓数据模型](#持仓数据模型)
- [错误处理](#错误处理)
- [使用示例](#使用示例)

## 概述

InvestRing 持仓管理模块提供了完整的投资组合持仓管理功能，支持多种资产类型的持仓跟踪、调整和管理。该模块基于 FastAPI 构建，提供 RESTful API 接口，支持持仓的新增、修改、删除、查询等操作。

### 核心功能特性
- **多资产支持**: 支持股票、基金、债券等多种金融产品持仓管理
- **实时计算**: 自动计算持仓成本、市值、收益等关键指标
- **净值型产品支持**: 专门针对净值型产品提供profit_loss、profit_loss_percent收益计算
- **资产类型识别**: 通过asset_type字段区分不同类型的资产
- **状态管理**: 完整的持仓生命周期管理，包括冻结、解冻等操作
- **批量操作**: 支持批量持仓调整和查询操作
- **数据验证**: 严格的参数验证和业务规则检查

## 认证要求

所有持仓管理API都需要通过JWT令牌认证。请求头中必须包含有效的Authorization令牌：

```http
Authorization: Bearer <your_jwt_token>
```

**章节来源**
- [positions.py](file://backend/app/routers/positions.py)

## 持仓基础操作

### 创建持仓
POST /api/portfolios/{portfolio_code}/positions

创建新的持仓记录，支持指定持仓数量、价格、手续费等详细信息。

**请求参数**
- `portfolio_code`: 投资组合代码（路径参数）
- `product_id`: 产品ID
- `shares`: 持仓数量
- `price`: 买入价格
- `fee`: 交易手续费
- `trade_date`: 交易日期

**响应示例**
```json
{
  "id": 1,
  "portfolio_code": "PORT001",
  "product_id": 123,
  "product_name": "贵州茅台",
  "asset_type": "stock",
  "shares": 100.00,
  "price": 15.50,
  "fee": 10.00,
  "cost_basis": 1560.00,
  "market_value": 1550.00,
  "profit_loss": -10.00,
  "profit_loss_percent": -0.64,
  "status": "active"
}
```

### 更新持仓
PUT /api/portfolios/{portfolio_code}/positions/{position_id}

更新现有持仓信息，支持修改数量、价格、状态等字段。

**权限要求**: 需要投资组合管理员权限

### 删除持仓
DELETE /api/portfolios/{portfolio_code}/positions/{position_id}

删除指定的持仓记录。删除前会进行业务规则验证。

**权限要求**: 需要投资组合管理员权限

**章节来源**
- [positions.py](file://backend/app/routers/positions.py)
- [position_service.py](file://backend/app/services/position_service.py)

## 持仓查询接口

### 获取持仓列表
GET /api/portfolios/{portfolio_code}/positions

获取投资组合的所有持仓列表，支持分页和过滤。

**查询参数**
- `page`: 页码（默认1）
- `size`: 每页数量（默认20）
- `status`: 持仓状态过滤（active/frozen/closed）
- `product_id`: 产品ID过滤
- `sort_by`: 排序字段（cost_basis/market_value/profit_loss）
- `order`: 排序方向（asc/desc）

**响应示例**
```json
{
  "items": [
    {
      "id": 1,
      "product_name": "贵州茅台",
      "product_code": "600519.SH",
      "asset_type": "stock",
      "shares": 100.00,
      "avg_cost": 156.00,
      "current_price": 155.00,
      "market_value": 15500.00,
      "cost_basis": 15600.00,
      "profit_loss": -100.00,
      "profit_loss_percent": -0.64,
      "status": "active",
      "last_updated": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "size": 20
}
```

### 获取单个持仓详情
GET /api/portfolios/{portfolio_code}/positions/{position_id}

获取指定持仓的详细信息，包括历史交易记录和收益分析。

### 投资者可用份额查询
GET /api/investors/{investor_id}/available-shares

查询投资者的可用份额信息，用于新持仓创建时的额度检查。

**权限要求**: 需要投资者查看权限

**章节来源**
- [positions.py](file://backend/app/routers/positions.py)
- [position_service.py](file://backend/app/services/position_service.py)

## 持仓调整接口

### 批量调整持仓
POST /api/portfolios/{portfolio_code}/positions/batch-adjust

批量调整多个持仓的数量或价格，支持事务性操作。

**请求体示例**
```json
{
  "adjustments": [
    {
      "position_id": 1,
      "action": "increase",
      "quantity": 50,
      "price": 15.80,
      "reason": "追加投资"
    },
    {
      "position_id": 2,
      "action": "decrease", 
      "quantity": 30,
      "price": 15.50,
      "reason": "部分止盈"
    }
  ]
}
```

### 持仓平仓
POST /api/portfolios/{portfolio_code}/positions/{position_id}/close

完全平掉指定持仓，执行卖出操作并计算最终收益。

**权限要求**: 需要投资组合交易权限

### 持仓部分减仓
POST /api/portfolios/{portfolio_code}/positions/{position_id}/reduce

部分减少持仓数量，保留剩余仓位。

**章节来源**
- [position_service.py](file://backend/app/services/position_service.py)

## 持仓状态管理

### 持仓冻结
POST /api/portfolios/{portfolio_code}/positions/{position_id}/freeze

冻结指定持仓，禁止交易操作但保持持仓记录。

**适用场景**
- 法律纠纷期间
- 监管要求限制
- 内部风控措施

### 持仓解冻
POST /api/portfolios/{portfolio_code}/positions/{position_id}/unfreeze

解冻之前被冻结的持仓，恢复正常的交易功能。

### 持仓状态变更
PUT /api/portfolios/{portfolio_code}/positions/{position_id}/status

直接修改持仓状态，支持从 active 到 frozen 或 closed 的状态转换。

**状态枚举值**
- `active`: 正常活跃状态
- `frozen`: 冻结状态
- `closed`: 已平仓状态

**章节来源**
- [position_service.py](file://backend/app/services/position_service.py)
- [portfolio_position.py](file://backend/app/models/portfolio_position.py)

## 持仓数据模型

### 持仓实体结构
```python
class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"
    
    id = Column(Integer, primary_key=True)
    portfolio_code = Column(String(50), ForeignKey("portfolios.code"))
    product_id = Column(Integer, ForeignKey("products.id"))
    shares = Column(Numeric(15, 2))
    avg_cost = Column(Numeric(15, 2))
    current_price = Column(Numeric(15, 2))
    market_value = Column(Numeric(15, 2))
    cost_basis = Column(Numeric(15, 2))
    profit_loss = Column(Numeric(15, 2))
    profit_loss_percent = Column(Numeric(10, 4))
    asset_type = Column(String(20))
    status = Column(String(20), default="active")
    last_updated = Column(DateTime)
```

### 投资者持仓关联
```python
class InvestorHolding(Base):
    __tablename__ = "investor_holdings"
    
    id = Column(Integer, primary_key=True)
    investor_id = Column(Integer, ForeignKey("investors.id"))
    portfolio_code = Column(String(50))
    product_id = Column(Integer)
    available_shares = Column(Numeric(15, 2))
    reserved_shares = Column(Numeric(15, 2))
    total_shares = Column(Numeric(15, 2))
```

### PositionResponse数据模型更新
**新增字段说明**
- `product_name`: 产品名称，便于前端展示
- `profit_loss`: 持仓盈亏金额，特别适用于净值型产品
- `profit_loss_percent`: 持仓盈亏百分比，标准化收益展示
- `asset_type`: 资产类型标识，区分股票、基金、债券等不同资产类别

**章节来源**
- [portfolio_position.py](file://backend/app/models/portfolio_position.py)
- [investor_holding.py](file://backend/app/models/investor_holding.py)
- [position.py](file://backend/app/schemas/position.py)

## 错误处理

### 常见错误类型
- `400 Bad Request`: 请求参数验证失败
- `401 Unauthorized`: 认证失败或令牌过期
- `403 Forbidden`: 权限不足
- `404 Not Found`: 资源不存在
- `409 Conflict`: 业务规则冲突
- `500 Internal Server Error`: 服务器内部错误

### 错误响应格式
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "持仓数量必须大于0",
    "details": {
      "field": "shares",
      "value": -10,
      "constraint": "positive_number"
    }
  }
}
```

**章节来源**
- [position_service.py](file://backend/app/services/position_service.py)

## 使用示例

### Python SDK 使用示例
```python
from investring_client import PositionClient

client = PositionClient(base_url="https://api.investring.com")
client.authenticate(token="your_jwt_token")

# 创建持仓
position = client.create_position(
    portfolio_code="PORT001",
    product_id=123,
    shares=100.0,
    price=15.50,
    fee=10.0
)

# 查询持仓列表
positions = client.get_positions(portfolio_code="PORT001", page=1, size=20)

# 调整持仓
client.adjust_position(
    portfolio_code="PORT001",
    position_id=1,
    action="increase",
    quantity=50,
    price=15.80
)
```

### cURL 命令示例
```bash
# 创建持仓
curl -X POST "https://api.investring.com/api/portfolios/PORT001/positions" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": 123,
    "shares": 100.0,
    "price": 15.50,
    "fee": 10.0
  }'

# 查询持仓
curl -X GET "https://api.investring.com/api/portfolios/PORT001/positions?page=1&size=20" \
  -H "Authorization: Bearer your_jwt_token"
```

**章节来源**
- [position_service.py](file://backend/app/services/position_service.py)
- [positions.py](file://backend/app/routers/positions.py)