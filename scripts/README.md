# 运维脚本

## 备份

```bash
python scripts/backup.py
```

默认输出 `data/backups/echohole-<UTC时间>.tar.gz`，包含：

- `echohole.db`：SQLite 数据库（用 sqlite3 backup API 安全备份）
- `uploads/`：图片目录
- `MANIFEST.txt`：备份元信息

选项：

- `--out DIR`：指定输出目录
- `--no-archive`：保留目录不打包

## 恢复

```bash
python scripts/restore.py data/backups/echohole-20260101-120000.tar.gz
python scripts/restore.py D:/backup/echohole-xxx --force
```

恢复前会校验目标数据库是否存在，默认拒绝覆盖；确认覆盖时加 `--force`。

恢复完成后脚本会打印账号数、公开帖子数、回应数、图片数，便于核对。

## 注意

- 脚本根据 `backend/config.py` 的配置决定数据库和图片目录位置，与运行中的应用保持一致。
- 建议在低峰期备份；sqlite3 backup API 支持在线备份，无需停止服务。
- 恢复会覆盖当前数据，生产环境请先自行备份现有数据库。
