import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.schemas.data_source import DataSourceResponse, DataSourceUpdate
from app.dependencies import get_current_user, get_current_admin
from app.models.product import Product

router = APIRouter()


def _mask_api_key(api_key: str) -> str:
    """
    脱敏 API Key
    显示前 4 位和后 4 位，中间用 * 替换
    """
    if not api_key or len(api_key) <= 8:
        return "***"
    return api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]


def _get_data_sources(db: Session) -> List[dict]:
    """
    获取数据源配置列表
    从 .env 文件和数据库读取数据源信息
    """
    # Tushare 数据源
    tushare_token = os.environ.get("TUSHARE_TOKEN", "")
    
    # 获取 Tushare 最后同步时间（从产品中获取最新的 last_sync_at）
    tushare_last_sync = db.query(Product).filter(
        Product.data_source == "tushare",
        Product.last_sync_at.isnot(None)
    ).order_by(Product.last_sync_at.desc()).first()

    # AkShare 数据源
    akshare_enabled = os.environ.get("AKSHARE_ENABLED", "true").lower() == "true"

    sources = [
        {
            "name": "tushare",
            "api_key": _mask_api_key(tushare_token) if tushare_token else None,
            "is_enabled": bool(tushare_token),
            "last_sync_at": tushare_last_sync.last_sync_at if tushare_last_sync else None,
            "created_at": None,
            "updated_at": None,
        },
        {
            "name": "akshare",
            "api_key": None,  # AkShare 不需要 API Key
            "is_enabled": akshare_enabled,
            "last_sync_at": None,
            "created_at": None,
            "updated_at": None,
        },
    ]

    return sources


@router.get("")
def get_data_sources(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    获取数据源配置列表
    
    返回 Tushare 和 AkShare 的配置信息
    API Key 会进行脱敏处理
    """
    return _get_data_sources(db)


@router.put("/{name}")
def update_data_source(
    name: str,
    data_source: DataSourceUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    更新数据源配置
    
    支持更新：
    - tushare: 更新 TUSHARE_TOKEN
    - akshare: 更新 AKSHARE_ENABLED
    """
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    
    if name == "tushare":
        # 更新 Tushare Token
        if data_source.api_key:
            _update_env_file(env_file, "TUSHARE_TOKEN", data_source.api_key)
            os.environ["TUSHARE_TOKEN"] = data_source.api_key
        
        return {
            "message": "Tushare 配置已更新",
            "name": "tushare",
            "is_enabled": bool(data_source.api_key or os.environ.get("TUSHARE_TOKEN")),
        }
    
    elif name == "akshare":
        # 更新 AkShare 启用状态
        if data_source.is_enabled is not None:
            _update_env_file(env_file, "AKSHARE_ENABLED", str(data_source.is_enabled).lower())
            os.environ["AKSHARE_ENABLED"] = str(data_source.is_enabled).lower()
        
        return {
            "message": "AkShare 配置已更新",
            "name": "akshare",
            "is_enabled": data_source.is_enabled,
        }
    
    else:
        raise HTTPException(status_code=404, detail=f"未知的数据源: {name}")


def _update_env_file(env_file: str, key: str, value: str) -> None:
    """
    更新 .env 文件中的配置项
    
    如果配置项已存在则更新，不存在则追加
    """
    lines = []
    key_found = False
    
    # 读取现有文件
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    
    # 查找并更新配置项
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped == key:
            lines[i] = f"{key}={value}\n"
            key_found = True
            break
    
    # 如果配置项不存在，追加到文件末尾
    if not key_found:
        lines.append(f"{key}={value}\n")
    
    # 写回文件
    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(lines)
