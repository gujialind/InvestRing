"""
配置与 token 管理

管理 ~/.ir/ 目录，读写 token.json 和 config 文件。
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def get_ir_dir() -> Path:
    """返回 ~/.ir/ 目录，不存在则创建"""
    ir_dir = Path.home() / ".ir"
    ir_dir.mkdir(parents=True, exist_ok=True)
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
        for line in config_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("base_url="):
                return line.split("=", 1)[1].strip().rstrip("/")

    return "http://localhost:8000"


def save_token(data: dict) -> None:
    """写入 token.json，设置权限 0o600"""
    token_file = get_ir_dir() / "token.json"
    token_file.write_text(json.dumps(data, ensure_ascii=False))
    try:
        os.chmod(token_file, 0o600)
    except OSError:
        pass  # Windows 不支持 chmod


def load_token() -> Optional[dict]:
    """
    读取 token.json。
    过期返回 None；临近过期（<24h）打印 stderr 警告。
    """
    token_file = get_ir_dir() / "token.json"
    if not token_file.exists():
        return None

    try:
        data = json.loads(token_file.read_text())
    except (json.JSONDecodeError, OSError):
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


def save_config(key: str, value: str) -> None:
    """写入配置项到 ~/.ir/config"""
    config_file = get_ir_dir() / "config"
    lines = []
    found = False
    if config_file.exists():
        for line in config_file.read_text().splitlines():
            if line.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key}={value}")
    config_file.write_text("\n".join(lines) + "\n")
