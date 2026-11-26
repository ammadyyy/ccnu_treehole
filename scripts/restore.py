"""回声洞恢复脚本（T-33）。

从备份（tar.gz 或目录）恢复数据库与 uploads 图片目录。

用法：
    python scripts/restore.py data/backups/echohole-20260101-120000.tar.gz
    python scripts/restore.py D:/backup/echohole-xxx --force
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402


def restore(backup_path: Path, force: bool = False) -> None:
    cfg = config.Config
    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise SystemExit(f"备份不存在: {backup_path}")

    # 解包到临时目录
    tmp: Path | None = None
    work = backup_path
    if backup_path.is_file():
        tmp = Path(tempfile.mkdtemp())
        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall(tmp)
        subs = [p for p in tmp.iterdir() if p.is_dir()]
        work = subs[0] if subs else tmp

    db_src = work / "echohole.db"
    if not db_src.exists():
        raise SystemExit(f"备份中缺少数据库: {db_src}")

    if cfg.DATABASE_PATH.exists() and not force:
        raise SystemExit(
            f"目标数据库已存在: {cfg.DATABASE_PATH}\n如确认覆盖，请加 --force"
        )

    cfg.ensure_dirs()

    # 恢复数据库
    if cfg.DATABASE_PATH.exists():
        cfg.DATABASE_PATH.unlink()
    shutil.copy2(db_src, cfg.DATABASE_PATH)

    # 恢复图片
    uploads_src = work / "uploads"
    if uploads_src.exists():
        if cfg.UPLOAD_DIR.exists():
            shutil.rmtree(cfg.UPLOAD_DIR)
        shutil.copytree(uploads_src, cfg.UPLOAD_DIR)

    # 校验
    conn = sqlite3.connect(str(cfg.DATABASE_PATH))
    try:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        posts = conn.execute("SELECT COUNT(*) FROM posts WHERE status='published'").fetchone()[0]
        comments = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
        images = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    finally:
        conn.close()

    if tmp is not None:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"恢复完成: {cfg.DATABASE_PATH}")
    print(f"账号 {users} / 公开帖子 {posts} / 回应 {comments} / 图片 {images}")
    print(f"图片目录: {cfg.UPLOAD_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description="回声洞恢复")
    parser.add_argument("backup", type=Path, help="备份 tar.gz 或目录")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的数据库")
    args = parser.parse_args()
    restore(args.backup, args.force)


if __name__ == "__main__":
    main()
