"""匿名回应（T-16）。"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

import auth
import db
from utils import seconds_since, utcnow

bp = Blueprint("comments", __name__)

COMMENT_MAX = 500
COMMENT_COOLDOWN = 30
PAGE_SIZE = 20


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _comment_payload(row, post_mask_id: int) -> dict:
    return {
        "id": row["id"],
        "body": row["body"],
        "mask": {"token": row["mask_token"], "status": row["mask_status"]},
        "isOp": bool(row["mask_id"] == post_mask_id),
        "createdAt": row["created_at"],
    }


@bp.post("/api/posts/<int:post_id>/comments")
@auth.login_required
def create_comment(post_id: int):
    mask_id = auth.get_current_mask_id()
    if mask_id is None:
        return _error("NO_MASK", "请先选择面具", 400)

    data = request.get_json(silent=True) or {}
    body = data.get("body")
    if not isinstance(body, str) or not body.strip():
        return _error("INVALID_BODY", "回应不能为空", 400)
    if len(body.strip()) > COMMENT_MAX:
        return _error("BODY_TOO_LONG", f"回应最多 {COMMENT_MAX} 字", 400)

    conn = db.get_connection()
    try:
        post = conn.execute(
            "SELECT * FROM posts WHERE id = ? AND status = 'published'", (post_id,)
        ).fetchone()
        if post is None:
            return _error("NOT_FOUND", "帖子不存在", 404)

        # 账号级 30 秒限速（users.last_comment_at，切换面具不重置）
        row = conn.execute(
            "SELECT last_comment_at FROM users WHERE id = ?", (g.user["id"],)
        ).fetchone()
        elapsed = seconds_since(row["last_comment_at"]) if row and row["last_comment_at"] else None
        if elapsed is not None and elapsed < COMMENT_COOLDOWN:
            wait = int(COMMENT_COOLDOWN - elapsed) + 1
            return _error("RATE_LIMITED", f"操作过于频繁，请 {wait} 秒后再试", 429)

        now = utcnow()
        cur = conn.execute(
            "INSERT INTO comments(post_id, mask_id, body, created_at) VALUES (?,?,?,?)",
            (post_id, mask_id, body, now),
        )
        comment_id = cur.lastrowid
        conn.execute("UPDATE users SET last_comment_at = ? WHERE id = ?", (now, g.user["id"]))
        conn.execute(
            "UPDATE posts SET comment_count = comment_count + 1 WHERE id = ?", (post_id,)
        )

        # 生成通知：他人回应我的帖子时通知帖子作者；自己回应自己不发
        author = conn.execute(
            "SELECT m.user_id AS author_id FROM posts p JOIN masks m ON p.mask_id = m.id "
            "WHERE p.id = ?",
            (post_id,),
        ).fetchone()
        author_id = author["author_id"] if author else None
        if author_id is not None and author_id != g.user["id"]:
            conn.execute(
                "INSERT INTO notifications"
                "(user_id, post_id, mask_id, comment_id, comment_deleted, type, is_read, content_deleted, created_at) "
                "VALUES (?,?,?,?,0,'post_comment',0,0,?)",
                (author_id, post_id, mask_id, comment_id, now),
            )

        conn.commit()

        mask = conn.execute(
            "SELECT id, token, status FROM masks WHERE id = ?", (mask_id,)
        ).fetchone()
        post_mask_id = post["mask_id"]
    finally:
        conn.close()

    return (
        jsonify(
            {
                "comment": {
                    "id": comment_id,
                    "body": body,
                    "mask": {"token": mask["token"], "status": mask["status"]},
                    "isOp": bool(mask_id == post_mask_id),
                    "createdAt": now,
                }
            }
        ),
        201,
    )


@bp.get("/api/posts/<int:post_id>/comments")
def list_comments(post_id: int):
    """回应列表，按时间从早到晚游标分页。"""
    cursor = request.args.get("cursor") or None
    cursor_at = cursor_id = None
    if cursor:
        parts = cursor.split(":")
        if len(parts) == 2:
            cursor_at = parts[0]
            try:
                cursor_id = int(parts[1])
            except ValueError:
                cursor_at = cursor_id = None

    conn = db.get_connection()
    try:
        post = conn.execute(
            "SELECT id, mask_id FROM posts WHERE id = ? AND status = 'published'", (post_id,)
        ).fetchone()
        if post is None:
            return _error("NOT_FOUND", "帖子不存在", 404)

        where = ["c.post_id = ?"]
        params: list = [post_id]
        if cursor_at and cursor_id:
            where.append("(c.created_at > ? OR (c.created_at = ? AND c.id > ?))")
            params += [cursor_at, cursor_at, cursor_id]

        sql = (
            "SELECT c.id, c.mask_id, c.body, c.created_at, m.token AS mask_token, m.status AS mask_status "
            "FROM comments c JOIN masks m ON c.mask_id = m.id "
            "WHERE " + " AND ".join(where) + " "
            "ORDER BY c.created_at ASC, c.id ASC LIMIT ?"
        )
        params.append(PAGE_SIZE + 1)
        rows = conn.execute(sql, params).fetchall()

        has_more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]

        post_mask_id = post["mask_id"]
        comments = [_comment_payload(r, post_mask_id) for r in rows]

        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = f"{last['created_at']}:{last['id']}"
    finally:
        conn.close()

    return jsonify({"comments": comments, "nextCursor": next_cursor})
