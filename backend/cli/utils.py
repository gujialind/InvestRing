"""
CLI 公共辅助函数

提供模型序列化、分页处理等通用工具。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional


def to_serializable(value: Any) -> Any:
    """将 SQLAlchemy 字段值转为可 JSON 序列化的类型"""
    if isinstance(value, Decimal):
        return float(round(value, 4))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def serialize_model(obj: Any, exclude: Optional[List[str]] = None) -> dict:
    """
    将 SQLAlchemy 模型实例转为 dict

    Args:
        obj: SQLAlchemy 模型实例
        exclude: 要排除的字段名列表
    """
    if obj is None:
        return None

    result = {}
    exclude = exclude or []
    for column in obj.__table__.columns:
        if column.name not in exclude:
            result[column.name] = to_serializable(getattr(obj, column.name))
    return result


def paginate(query, page: int = 1, page_size: int = 20, fetch_all: bool = False):
    """
    通用分页查询

    Returns:
        (items, total, page, page_size)
    """
    total = query.count()
    if fetch_all:
        items = query.all()
        page_size = total
    else:
        items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total, page, page_size


def parse_date(value: str) -> date:
    """解析 YYYY-MM-DD 格式的日期字符串"""
    if not value:
        return None
    return date.fromisoformat(value)


def pagination_meta(total: int, page: int, page_size: int) -> dict:
    """生成分页元数据"""
    return {"total": total, "page": page, "page_size": page_size}
