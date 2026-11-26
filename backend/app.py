"""回声洞后端入口。

启动时加载配置、确保数据目录存在、执行数据库迁移。
生产由 Waitress + systemd 承载（见 T-32），开发用 Flask 内置服务器。
"""
from __future__ import annotations

from flask import Flask, jsonify, send_from_directory

import auth
import config
import db
import masks
import posts

FRONTEND_DIST = config.BASE_DIR / "frontend" / "dist"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.Config.SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = config.Config.COOKIE_SECURE

    app.register_blueprint(auth.bp)
    app.register_blueprint(masks.bp)
    app.register_blueprint(posts.bp)

    # 同源静态服务：生产构建产物由 Flask 提供，SPA 路由回退到 index.html。
    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def serve_frontend(path: str):
        if path.startswith("api/"):
            return jsonify({"error": {"code": "NOT_FOUND", "message": "接口不存在"}}), 404
        dist_path = FRONTEND_DIST / path
        if path and dist_path.is_file():
            return send_from_directory(FRONTEND_DIST, path)
        index = FRONTEND_DIST / "index.html"
        if index.is_file():
            return send_from_directory(FRONTEND_DIST, "index.html")
        return (
            jsonify({"error": {"code": "NO_FRONTEND", "message": "前端未构建，请先运行 npm run build"}}),
            503,
        )

    return app


app = create_app()


@app.get("/api/health")
def health():
    """健康检查，供前端联调与部署探活。"""
    return jsonify({"status": "ok", "service": "echohole"})


if __name__ == "__main__":
    config.Config.ensure_dirs()
    migrated = db.migrate()
    if migrated:
        print(f"[echohole] 应用迁移: {', '.join(migrated)}")
    app.run(
        host=config.Config.HOST,
        port=config.Config.PORT,
        debug=config.is_dev(),
    )
