# 回声洞（ccnu_treehole）

面向本校学生的匿名校园树洞社区。

用户注册账号后领取随机「面具」，以面具身份在树洞墙发帖、上传图片、回应他人，并接收自己帖子收到新回应的通知。产品把身份拆成两层：**对外只有随机面具**（帖子与回应不暴露账号），**对内只有账号**（面具到账号的映射仅管理员在受控场景下可查）。目标是在「可以匿名说真话」与「出了事找得到人」之间取得平衡。

> 2026 软件需求分析与建模课程项目：需求规格说明书 + 可运行原型。

## 技术栈

| 层次 | 技术 |
|---|---|
| 后端 | Python 3.13+ · Flask 3 · SQLite（FTS5 + trigram 全文检索）· Waitress |
| 前端 | Vite · React 19 · TypeScript · React Router 7（data router）· Tailwind CSS 4 |
| 图片处理 | Pillow（魔数校验、EXIF 校正与剥离、WebP 转换、缩略图、动图） |
| 部署 | PVE LXC（Debian 12）+ systemd |

## 功能特性

### 账号与身份
- 邮箱 + 密码注册/登录/登出（Werkzeug PBKDF2，httpOnly + SameSite=Lax Cookie 会话，不使用 JWT）
- 每个账号最多 5 个可用面具，面具名全局唯一且**永久不复用**
- 登录后选择「当前面具」，期间统一使用，可在个人中心/面具页随时切换
- 面具销毁后历史内容保留并标记「已销毁面具」；账号注销后统一显示「已注销面具」
- 账号设置：修改密码（保留当前会话、注销其他会话）、注销账号（邮箱释放、可重新注册且与旧账号隔离）

### 内容
- 发帖：标题（1–50 字，单行）+ 正文（1–2000 字）+ 1–2 个固定标签，可附最多 3 张图片
- 图片：魔数校验、EXIF 方向校正与元数据剥离、统一转 WebP（质量 85）、生成缩略图（动图取第一帧）、UUID 命名
- 树洞墙：最新（`created_at + id` 游标分页）/ 24 小时热门（8 份进程内缓存，5 分钟 TTL）/ 单标签筛选
- 帖子详情：标题 → 横向相册（≤60vh、不裁剪、桌面按钮+键盘 / 移动端滑动、大图预览）→ 正文 → 回应区
- 单层匿名回应（1–500 字），发帖面具回应显示「楼主」标记
- 删除：帖子走墓碑机制（清空正文、删回应与图片记录、保留 `status=deleted`），提交后再删磁盘文件
- 搜索：单/双字用参数化 `LIKE`，三字及以上用 FTS5 `trigram`；覆盖标题/正文/回应，按帖聚合去重
- 通知：他人回应我的帖子时生成，逐条已读 + 全部已读，导航 30 秒轮询 + 聚焦刷新

### 治理
- 举报：仅登录用户，固定原因 + 可选说明，每分钟最多 3 次，不能举报自己的内容，不自动隐藏
- 举报队列/详情：按待处理数排序、原因与状态筛选、被举报内容上下文、内部备注（可追加不可改删）
- 举报处理：保留 / 删除，需固定理由 + ≥10 字说明 + 二次确认，同目标统一结案，写审计日志
- 两级管理员：唯一超级管理员 + 普通管理员（创建/停用/恢复/重置密码）
- 内容管理：关键词搜索、类型与已注销面具筛选、直接删除
- 面具映射查看：普通面具不记日志，已注销面具记审计日志
- 审计日志：只读、不导出，普通管理员只看自己，超级管理员看全部

## 目录结构

```
ccnu_treehole/
├── backend/                  # Flask API
│   ├── app.py                # 应用入口（蓝图注册 + SPA 同源静态服务）
│   ├── config.py             # 配置（.env 读取、数据目录）
│   ├── db.py                 # 连接与编号化迁移
│   ├── utils.py              # UTC 时间等通用工具
│   ├── auth.py               # 注册/登录/登出/会话/当前面具
│   ├── masks.py              # 面具领取/销毁/切换
│   ├── posts.py              # 发帖/列表/热门/详情/搜索/删除
│   ├── comments.py           # 匿名回应
│   ├── notifications.py      # 通知列表与已读
│   ├── account.py            # 修改密码/注销
│   ├── images.py             # 图片处理
│   ├── reports.py            # 举报提交/队列/处理/备注
│   ├── admin.py              # 管理员体系 + 统计 + 审计
│   ├── content.py            # 内容管理
│   ├── identity.py           # 面具映射查看
│   ├── seed.py               # 演示种子数据
│   ├── requirements.txt
│   └── migrations/           # 001_init / 002_rate_limits / 003_login_meta
├── frontend/                 # Vite + React
│   └── src/
│       ├── router.tsx        # createBrowserRouter + ScrollRestoration
│       ├── lib/              # api 封装 / auth 上下文 / 类型
│       ├── components/       # Navbar / ReportDialog / ui 组件
│       └── pages/            # 15 个页面（含 admin/ 5 个后台页）
├── scripts/                  # backup.py / restore.py + 说明
├── deploy/                   # systemd unit + LXC 部署说明
├── docs/                     # 需求规格说明书 + 开发任务卡片
├── tests/acceptance.py       # 全量验收测试（19 个用例）
├── data/                     # 运行时数据（数据库、图片），git 忽略
├── .env.example
└── README.md
```

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env      # 按需修改
python app.py
```

默认监听 `http://127.0.0.1:8000`，健康检查 `GET /api/health`。首次启动自动执行数据库迁移。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

默认 `http://127.0.0.1:5173`，`/api/*` 通过 Vite 代理到后端 8000 端口。

### 3. 灌入演示数据（可选）

```bash
cd backend
python seed.py
```

生成：超级管理员、12 个测试账号、29 个面具、60 帖、约 200 回应、200 条通知、敏感词。**幂等可重复执行**。

| 角色 | 账号 | 密码 |
|---|---|---|
| 超级管理员 | `admin@healing.local` | `Admin1234` |
| 测试用户 | `seed01@test.com` ~ `seed12@test.com` | `Seed1234` |

### 4. 生产模式（同源部署）

```bash
cd frontend && npm run build     # 产物到 frontend/dist
cd ../backend && python app.py   # Flask 同时提供 API 与前端静态文件
```

前端构建产物由 Flask 同源提供，SPA 路由自动回退到 `index.html`，无需额外反向代理。

## 配置

复制 `.env.example` 为 `.env`：

| 键 | 说明 |
|---|---|
| `APP_ENV` | `demo` / `dev` / `prod` |
| `APP_URL` | 站点访问地址（生成分享链接等） |
| `HOST` / `PORT` | 监听地址与端口 |
| `DATA_DIR` | 数据根目录 |
| `DATABASE_PATH` | SQLite 文件路径 |
| `UPLOAD_DIR` | 图片目录 |
| `COOKIE_SECURE` | 接入 HTTPS 后置 `true` |
| `SECRET_KEY` | 会话签名密钥，生产必须改为随机值 |

## 测试

```bash
# 在仓库根目录执行
python tests/acceptance.py
```

覆盖 UC-01~UC-13 主流程 + 8 个边界用例（限速、权限、删除一致性、图片、通知），当前 **19/19 通过**。使用临时数据库与上传目录，不影响真实数据。

前端构建校验：

```bash
cd frontend && npm run build     # 同时可用 npx tsc --noEmit 做类型检查
```

## 部署

详见 [`deploy/README.md`](deploy/README.md)：PVE LXC 内创建用户与目录、安装依赖、构建前端、初始化数据库与管理员、安装 `echohole.service`、systemd 启停与开机自启、校园网访问验证、后续接入域名/HTTPS 的迁移方式。

## 备份与恢复

详见 [`scripts/README.md`](scripts/README.md)：

```bash
python scripts/backup.py                                    # 备份数据库 + uploads（tar.gz）
python scripts/restore.py data/backups/echohole-xxx.tar.gz --force   # 恢复
```

## 需求文档

- [软件需求规格说明书 v0.5](docs/软件需求规格说明书-v0.5.md)：功能需求 FR-01~FR-15、非功能需求、数据模型、页面与接口清单、用例、追溯矩阵
- [开发任务卡片](docs/开发任务卡片.md)：34 个任务的拆分、验收标准与前置依赖

## 已知限制

- 演示阶段仅监听校园网 `IP:端口`，未配置域名与 HTTPS（接入方式见部署文档）。
- 忘记密码与修改邮箱为保留入口，点击显示「开发中，敬请期待」（`POST /api/auth/change-email` 返回 501）。
- 敏感词待审、账号封禁不在本期范围（表结构预留）。
