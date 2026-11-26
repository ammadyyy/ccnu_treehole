# 回声洞（ccnu_treehole）

面向本校学生的匿名校园树洞社区。用户注册账号后领取随机面具，以面具身份在树洞墙发帖、上传图片、回应，并接收帖子收到新回应的通知。

2026 软件需求分析与建模作业。

## 技术栈

| 层次 | 技术 |
|---|---|
| 后端 | Python 3.13+ · Flask 3 · SQLite · Waitress |
| 前端 | Vite · React 19 · TypeScript · React Router 7 · Tailwind CSS 4 |
| 部署 | PVE LXC + systemd |

## 目录结构

```
ccnu_treehole/
├── backend/            # Flask API 后端
│   ├── app.py          # 应用入口（最小骨架）
│   └── requirements.txt
├── frontend/           # Vite + React 前端
│   ├── src/
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── data/               # 运行时数据（数据库、图片，被 git 忽略）
├── .env.example        # 环境变量示例
└── README.md
```

## 快速开始

### 后端

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

后端默认监听 `http://127.0.0.1:8000`，健康检查：`GET /api/health`。

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认监听 `http://127.0.0.1:5173`，`/api/*` 会代理到后端 8000 端口。

## 配置

复制 `.env.example` 为 `.env`，按需修改。全部配置键见 `.env.example`。

## 文档

- 需求规格说明书：`F:\myweb\回声洞-软件需求规格说明书-v0.5.md`
- 开发任务卡片：`F:\myweb\回声洞-开发任务卡片.md`
