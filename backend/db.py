"""SQLite 连接与编号化迁移（T-02）。

迁移文件放在 migrations/ 目录，按文件名排序逐个应用；
已应用的迁移记录在 _migrations 表，避免重复执行。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import config
from utils import utcnow

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """打开数据库连接，开启外键约束，返回 Row 行工厂连接。"""
    path = db_path or str(config.Config.DATABASE_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _applied(conn: sqlite3.Connection) -> set[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _migrations (filename TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    return {row["filename"] for row in conn.execute("SELECT filename FROM _migrations").fetchall()}


def migrate(db_path: str | None = None) -> list[str]:
    """按序应用 migrations/*.sql，返回本次新应用的迁移文件名列表。"""
    config.Config.ensure_dirs()
    conn = get_connection(db_path)
    try:
        applied = _applied(conn)
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        newly: list[str] = []
        now = utcnow()
        for f in files:
            if f.name in applied:
                continue
            sql = f.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO _migrations(filename, applied_at) VALUES (?, ?)", (f.name, now)
            )
            conn.commit()
            applied.add(f.name)
            newly.append(f.name)
        return newly
    finally:
        conn.close()
