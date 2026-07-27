"""
配置与 token 管理

管理 ~/.ir/ 目录，读写 token.json、config 和本地缓存。
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def get_ir_dir() -> Path:
    """返回 ~/.ir/ 目录（权限 0700），不存在则创建"""
    ir_dir = Path.home() / ".ir"
    ir_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    return ir_dir


def get_base_url() -> str:
    """
    获取服务端 base_url。
    优先级: IR_BASE_URL 环境变量 > ~/.ir/config > 默认 localhost:8000
    """
    env_url = os.environ.get("IR_BASE_URL")
    if env_url:
        return env_url.rstrip("/")

    config_file = get_ir_dir() / "config"
    if config_file.exists():
        for line in config_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("base_url="):
                return line.split("=", 1)[1].strip().rstrip("/")

    return "http://localhost:8000"


def save_token(data: dict) -> None:
    """写入 token.json，创建时即为 0600（无权限窗口）"""
    token_file = get_ir_dir() / "token.json"
    content = json.dumps(data, ensure_ascii=False)
    # 先创建 0600 的临时文件再原子 rename，避免默认 umask 下短暂可读窗口
    tmp_file = token_file.with_suffix(".json.tmp")
    fd = os.open(tmp_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_file, token_file)
    except OSError:
        # 降级：直接写入后补 chmod（Windows 等不支持的平台）
        token_file.write_text(content, encoding="utf-8")
        try:
            os.chmod(token_file, 0o600)
        except OSError:
            pass


def load_token() -> Optional[dict]:
    """
    读取 token.json。
    过期返回 None；临近过期（<24h）打印 stderr 警告。
    """
    token_file = get_ir_dir() / "token.json"
    if not token_file.exists():
        return None

    try:
        data = json.loads(token_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None

    expires_at = data.get("expires_at")
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at)
            # 如果没有时区信息，假设为 UTC
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if exp_dt <= now:
                return None  # 已过期
            remaining = (exp_dt - now).total_seconds()
            if remaining < 86400:  # < 24h
                hours = remaining / 3600
                print(
                    f"[警告] token 将在 {hours:.1f} 小时后过期，建议重新登录: ir auth login",
                    file=sys.stderr,
                )
        except (ValueError, TypeError):
            pass

    return data


def clear_token() -> None:
    """删除 token.json"""
    token_file = get_ir_dir() / "token.json"
    if token_file.exists():
        token_file.unlink()


def load_config() -> dict:
    """读取 ~/.ir/config 全部配置项（key=value 格式）"""
    config_file = get_ir_dir() / "config"
    result = {}
    if config_file.exists():
        for line in config_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def save_config(key: str, value: str) -> None:
    """写入配置项到 ~/.ir/config"""
    config_file = get_ir_dir() / "config"
    lines = []
    found = False
    if config_file.exists():
        for line in config_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key}={value}")
    config_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- 本地缓存（目前用于交易日历） ----------

def _cache_dir() -> Path:
    cache_dir = get_ir_dir() / "cache"
    cache_dir.mkdir(mode=0o700, exist_ok=True)
    return cache_dir


def load_cache(name: str, ttl_seconds: int) -> Optional[Any]:
    """读取本地缓存，超过 TTL 或损坏时返回 None"""
    cache_file = _cache_dir() / f"{name}.json"
    if not cache_file.exists():
        return None
    try:
        wrapper = json.loads(cache_file.read_text(encoding="utf-8"))
        if time.time() - wrapper["cached_at"] > ttl_seconds:
            return None
        return wrapper["data"]
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, OSError):
        return None


def save_cache(name: str, data: Any) -> None:
    """写入本地缓存（失败静默忽略，缓存不影响主流程）"""
    try:
        cache_file = _cache_dir() / f"{name}.json"
        cache_file.write_text(json.dumps({"cached_at": time.time(), "data": data}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def clear_cache(prefix: str = "") -> int:
    """清除缓存文件（可按前缀），返回删除数量"""
    count = 0
    for f in _cache_dir().glob(f"{prefix}*.json"):
        try:
            f.unlink()
            count += 1
        except OSError:
            pass
    return count
