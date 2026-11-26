"""回声洞后端入口（最小骨架）。

后续任务会在此基础上扩展：配置加载、数据库、蓝图、认证等。
"""
from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/api/health")
def health():
    """健康检查，供前端联调与部署探活。"""
    return jsonify({"status": "ok", "service": "echohole"})


if __name__ == "__main__":
    # 开发用；生产由 Waitress + systemd 承载（见 T-32）
    app.run(host="0.0.0.0", port=8000, debug=True)
