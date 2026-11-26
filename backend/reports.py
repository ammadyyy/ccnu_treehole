"""举报提交与限频（T-22）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, jsonify, request

import auth
import db
from utils import utcnow

bp = Blueprint("reports", __name__)

REPORT_REASONS = ("广告或垃圾信息", "辱骂攻击", "色情低俗", "泄露隐私", "违法违规", "其他")
DETAIL_MAX = 200
REPORT_RATE_LIMIT = 3          # 每分钟最多 3 次
REPORT_RATE_WINDOW = 60        # 秒


def _err(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _window_start() -> str:
    dt = datetime.now(timezone.utc) - timedelta(seconds=REPORT_RATE_WINDOW)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@bp.post("/api/reports")
@auth.login_required
def create_report():
    data = request.get_json(silent=True) or {}
    target_type = data.get("targetType")      # post | comment
    target_id = data.get("targetId")
    reason = data.get("reason") or ""
    detail = data.get("detail") or ""

    if target_type not in ("post", "comment"):
        return _err("INVALID_TARGET", "举报目标类型无效", 400)
    if not isinstance(target_id, int) or target_id <= 0:
        return _err("INVALID_TARGET", "举报目标无效", 400)
    if reason not in REPORT_REASONS:
        return _err("INVALID_REASON", "举报原因无效", 400)
    if len(detail) > DETAIL_MAX:
        return _err("DETAIL_TOO_LONG", f"补充说明最多 {DETAIL_MAX} 字", 400)

    conn = db.get_connection()
    try:
        # 目标存在且公开
        if target_type == "post":
            target = conn.execute(
                "SELECT p.id, p.mask_id, m.user_id AS author_user_id "
                "FROM posts p JOIN masks m ON p.mask_id = m.id "
                "WHERE p.id = ? AND p.status = 'published'",
                (target_id,),
            ).fetchone()
        else:
            target = conn.execute(
                "SELECT c.id, c.mask_id, m.user_id AS author_user_id "
                "FROM comments c JOIN masks m ON c.mask_id = m.id "
                "WHERE c.id = ?",
                (target_id,),
            ).fetchone()
        if target is None:
            return _err("NOT_FOUND", "内容不存在或已删除", 404)

        # 不能举报自己的内容
        if target["author_user_id"] == g.user["id"]:
            return _err("SELF_REPORT", "不能举报自己的内容", 400)

        # 每分钟最多 3 次限速
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM reports WHERE reporter_user_id = ? AND created_at >= ?",
            (g.user["id"], _window_start()),
        ).fetchone()["c"]
        if count >= REPORT_RATE_LIMIT:
            return _err("RATE_LIMITED", "举报过于频繁，请稍后再试", 429)

        mask_id = auth.get_current_mask_id()
        now = utcnow()
        conn.execute(
            "INSERT INTO reports(target_type, target_id, reporter_user_id, reporter_email_snapshot, "
            "reporter_mask_id, reporter_ip, reason, detail, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,'open',?)",
            (target_type, target_id, g.user["id"], g.user["email"], mask_id,
             request.remote_addr, reason, detail or None, now),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True, "message": "已收到举报，等待处理"}), 201
