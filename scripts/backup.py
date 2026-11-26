"""回声洞备份脚本（T-33）。

备份内容：
- SQLite 数据库（使用 sqlite3 backup API，安全处理 WAL/并发）
- uploads 图片目录

默认打包为 tar.gz，输出到 data/backups/。

用法：
    python scripts/backup.py
    python scripts/backup.py --out D:/backup
    python scripts/backup.py --no-archive   # 保留目录不打包
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402


def make_backup(out_dir: Path | None = None, archive: bool = True) -> Path:
    cfg = config.Config
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    if out_dir is None:
        out_dir = cfg.DATA_DIR / "backups" / f"echohole-{ts}"
    out_dir = Path(out_dir)
    if out_dir.suffix == ".tar.gz":
        out_dir = out_dir.with_suffix("").with_suffix("")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 数据库：sqlite3 backup API 能安全处理 WAL 和并发写
    db_dst = out_dir / "echohole.db"
    src = sqlite3.connect(str(cfg.DATABASE_PATH))
    try:
        dst = sqlite3.connect(str(db_dst))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    # 2. 图片目录
    uploads_present = cfg.UPLOAD_DIR.exists()
    if uploads_present:
        shutil.copytree(cfg.UPLOAD_DIR, out_dir / "uploads")

    # 3. 清单
    (out_dir / "MANIFEST.txt").write_text(
        f"created_at={ts}\n"
        f"database={db_dst.name}\n"
        f"uploads_present={uploads_present}\n"
        f"source_db={cfg.DATABASE_PATH}\n",
        encoding="utf-8",
    )

    if not archive:
        return out_dir

    tar_path = out_dir.parent / f"{out_dir.name}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(out_dir, arcname=out_dir.name)
    shutil.rmtree(out_dir)
    return tar_path


def main() -> None:
    parser = argparse.ArgumentParser(description="回声洞备份")
    parser.add_argument("--out", type=Path, default=None, help="输出目录（默认 data/backups/）")
    parser.add_argument("--no-archive", action="store_true", help="不打包，保留目录")
    args = parser.parse_args()

    result = make_backup(args.out, archive=not args.no_archive)
    if result.is_dir():
        size = sum(p.stat().st_size for p in result.rglob("*") if p.is_file())
    else:
        size = result.stat().st_size
    print(f"备份完成: {result}")
    print(f"大小: {size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
