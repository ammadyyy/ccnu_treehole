"""配置管理（T-03）。

从项目根目录的 .env 读取配置，缺失时使用安全开发默认值。
数据库、图片等路径完全由配置决定，无硬编码绝对路径。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（backend/ 的上一级，即仓库根）
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# 加载 .env（文件不存在时静默，使用下方默认值）
load_dotenv(ENV_FILE)


def _resolve_path(value: str) -> Path:
    """把相对路径解析为基于项目根目录的绝对路径；绝对路径原样保留。"""
    p = Path(value)
    if not p.is_absolute():
        p = BASE_DIR / p
    return p


def _as_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes", "on")


class Config:
    """集中式配置。属性在模块导入时计算一次。"""

    APP_ENV = os.getenv("APP_ENV", "demo")
    APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8000")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    DATA_DIR = _resolve_path(os.getenv("DATA_DIR", "data"))
    DATABASE_PATH = _resolve_path(os.getenv("DATABASE_PATH", str(DATA_DIR / "echohole.db")))
    UPLOAD_DIR = _resolve_path(os.getenv("UPLOAD_DIR", str(DATA_DIR / "uploads")))

    COOKIE_SECURE = _as_bool(os.getenv("COOKIE_SECURE", "false"))

    @classmethod
    def ensure_dirs(cls) -> None:
        """启动时确保数据目录与上传目录存在。"""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        # 确保数据库父目录存在
        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def is_dev() -> bool:
    return Config.APP_ENV in ("dev", "demo")
