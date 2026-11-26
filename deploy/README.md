# 部署说明（PVE LXC + systemd + Waitress）

目标环境：PVE 上的 Debian 12 LXC 容器，校园网内通过 `IP:端口` 访问。

## 1. 创建运行用户与目录

```bash
useradd --system --create-home --shell /usr/sbin/nologin echohole
mkdir -p /srv/echohole
chown ec（略）chohole:echohole /srv/echohole
```

> 上面命令中的中文括号是占位，请用 `chown echohole:echohole /srv/echohole`。

## 2. 部署代码

```bash
cd /srv/echohole
git clone https://github.com/ammadyyy/ccnu_treehole.git app
chown -R echohole:echohole /srv/echohole/app
```

## 3. 创建虚拟环境并安装依赖

```bash
cd /srv/echohole/app/backend
python3 -m venv /srv/echohole/venv
/srv/echohole/venv/bin/pip install --upgrade pip
/srv/echohole/venv/bin/pip install -r requirements.txt
```

## 4. 配置 .env

```bash
cd /srv/echohole/app
cp .env.example .env
```

编辑 `.env`，至少设置：

```dotenv
APP_ENV=prod
APP_URL=http://<校园网服务器IP>:8000
HOST=0.0.0.0
PORT=8000
DATA_DIR=/srv/echohole/data
DATABASE_PATH=/srv/echohole/data/echohole.db
UPLOAD_DIR=/srv/echohole/data/uploads
COOKIE_SECURE=false
SECRET_KEY=<随机长字符串>
```

生成随机密钥：

```bash
python3 -c "import secrets;print(secrets.token_urlsafe(48))"
```

## 5. 构建前端

```bash
cd /srv/echohole/app/frontend
npm ci
npm run build
```

构建产物在 `frontend/dist/`，由 Flask 同源静态服务提供（无需额外反向代理）。

## 6. 初始化数据库与管理员

```bash
cd /srv/echohole/app/backend
/srv/echohole/venv/bin/python -c "import db; print(db.migrate())"
```

创建超级管理员（按实际实现调整，示例）：

```bash
/srv/echohole/venv/bin/python -c "import admin; admin.create_super_admin('admin@example.com','ChangeMe123')"
```

## 7. 安装 systemd 服务

```bash
cp /srv/echohole/app/deploy/echohole.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now echohole
systemctl status echohole
```

服务日志：

```bash
journalctl -u echohole -f
```

## 8. 验证

```bash
curl -s http://127.0.0.1:8000/api/health
# 期望：{"status":"ok","service":"echohole"}
```

在校园网另一台设备访问 `http://<服务器IP>:8000/`，应能看到树洞墙页面。

## 9. 数据目录与备份

- 数据库：`/srv/echohole/data/echohole.db`
- 图片：`/srv/echohole/data/uploads/`
- 备份：`python scripts/backup.py`（见 `scripts/README.md`）

重启服务不会影响数据文件：

```bash
systemctl restart echohole
```

## 10. 更新发布

```bash
cd /srv/echohole/app
git pull
cd backend && /srv/echohole/venv/bin/pip install -r requirements.txt
cd ../frontend && npm ci && npm run build
cd ../backend && /srv/echohole/venv/bin/python -c "import db; print(db.migrate())"
systemctl restart echohole
```

## 后续迁移到域名/HTTPS

当前直接监听 `0.0.0.0:8000`。将来接入域名时，可在前面加 Caddy/Nginx 做反向代理并终止 TLS，只需：

- 反向代理转发到 `127.0.0.1:8000`；
- 修改 `.env` 的 `APP_URL=https://your.domain`；
- 将 `COOKIE_SECURE` 设为 `true`；
- 重启 `echohole` 服务。
