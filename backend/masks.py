"""面具领取与销毁（T-07）。"""
from __future__ import annotations

import secrets

from flask import Blueprint, g, jsonify, request

import auth
import db
from utils import utcnow

bp = Blueprint("masks", __name__)

# 剔除易混字符（0/o/1/l/i）后的字符集，符合「匿名者·xxxx」的 4 位随机串
MASK_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"
MASK_LIMIT = 5
MAX_GEN_RETRY = 5


def _gen_token() -> str:
    return "匿名者·" + "".join(secrets.choice(MASK_CHARS) for _ in range(4))


def _mask_payload(row) -> dict:
    return {
        "id": row["id"],
        "token": row["token"],
        "status": row["status"],
        "postCount": row["post_count"],
        "commentCount": row["comment_count"],
        "createdAt": row["created_at"],
        "destroyedAt": row["destroyed_at"],
    }


@bp.get("/api/masks")
@auth.login_required
def list_masks():
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT m.*, "
            "(SELECT COUNT(*) FROM posts p WHERE p.mask_id = m.id AND p.status = 'published') AS post_count, "
            "(SELECT COUNT(*) FROM comments c WHERE c.mask_id = m.id) AS comment_count "
            "FROM masks m WHERE m.user_id = ? "
            "ORDER BY (m.status = 'active') DESC, m.created_at ASC",
            (g.user["id"],),
        ).fetchall()
        masks = [_mask_payload(r) for r in rows]
    finally:
        conn.close()
    return jsonify({"masks": masks})


@bp.post("/api/masks")
@auth.login_required
def create_mask():
    conn = db.get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM masks WHERE user_id = ? AND status = 'active'",
            (g.user["id"],),
        ).fetchone()["c"]
        if count >= MASK_LIMIT:
            return jsonify({"error": {"code": "MASK_LIMIT", "message": "最多只能持有 5 个面具"}}), 409

        token = None
        for _ in range(MAX_GEN_RETRY):
            candidate = _gen_token()
            if conn.execute("SELECT id FROM masks WHERE token = ?", (candidate,)).fetchone() is None:
                token = candidate
                break
        if token is None:
            return jsonify({"error": {"code": "MASK_GEN_FAILED", "message": "面具生成失败，请重试"}}), 500

        now = utcnow()
        cur = conn.execute(
            "INSERT INTO masks(user_id, token, status, created_at) VALUES (?,?,?,?)",
            (g.user["id"], token, "active", now),
        )
        conn.commit()
        mask_id = cur.lastrowid
    finally:
        conn.close()
    return jsonify({"mask": {"id": mask_id, "token": token, "status": "active"}}), 201


@bp.delete("/api/masks/<int:mask_id>")
@auth.login_required
def destroy_mask(mask_id: int):
    conn = db.get_connection()
    try:
        mask = conn.execute(
            "SELECT * FROM masks WHERE id = ? AND user_id = ?", (mask_id, g.user["id"])
        ).fetchone()
        if mask is None:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "面具不存在"}}), 404
        if mask["status"] == "destroyed":
            return jsonify({"error": {"code": "ALREADY_DESTROYED", "message": "面具已销毁"}}), 409

        now = utcnow()
        conn.execute("UPDATE masks SET status = 'destroyed', destroyed_at = ? WHERE id = ?", (now, mask_id))
        # 销毁的是当前面具时，清空所有会话中指向该面具的 current_mask_id
        conn.execute("UPDATE sessions SET current_mask_id = NULL WHERE current_mask_id = ?", (mask_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.post("/api/session/current-mask")
@auth.login_required
def set_current_mask_view():
    """设置当前登录期间使用的面具（T-08）。"""
    data = request.get_json(silent=True) or {}
    mask_id = data.get("maskId")
    if mask_id is None:
        return jsonify({"error": {"code": "INVALID", "message": "请指定面具"}}), 400

    conn = db.get_connection()
    try:
        mask = conn.execute(
            "SELECT * FROM masks WHERE id = ? AND user_id = ? AND status = 'active'",
            (mask_id, g.user["id"]),
        ).fetchone()
    finally:
        conn.close()

    if mask is None:
        return jsonify({"error": {"code": "MASK_UNAVAILABLE", "message": "面具不可用"}}), 404

    auth.set_current_mask(mask_id)
    return jsonify(
        {"ok": True, "currentMask": {"id": mask_id, "token": mask["token"], "status": "active"}}
    )
