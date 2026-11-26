"""站内通知（T-20 列表 + T-21 已读）。

通知生成已在 comments.py 的回应创建逻辑中实现（T-16）：
- 他人回应我的帖子时，给帖子作者生成一条通知；
- 自己回应自己不发；每条回应一条，不合并。
本模块提供通知列表与已读接口。
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

import auth
import db

bp = Blueprint("notifications", __name__)

PAGE_SIZE = 20


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _notification_payload(row) -> dict:
    post_deleted = row["content_deleted"] or row["post_status"] == "deleted"
    return {
        "id": row["id"],
        "mask": {"token": row["mask_token"], "status": row["mask_status"]},
        "postId": row["post_id"],
        "postTitle": None if post_deleted else row["post_title"],
        "contentDeleted": bool(post_deleted),
        "commentDeleted": bool(row["comment_deleted"]),
        "isRead": bool(row["is_read"]),
        "createdAt": row["created_at"],
    }


@bp.get("/api/notifications")
@auth.login_required
def list_notifications():
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
        unread = conn.execute(
            "SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND is_read = 0",
            (g.user["id"],),
        ).fetchone()["c"]

        where = ["n.user_id = ?"]
        params: list = [g.user["id"]]
        if cursor_at and cursor_id:
            where.append("(n.created_at < ? OR (n.created_at = ? AND n.id < ?))")
            params += [cursor_at, cursor_at, cursor_id]

        sql = (
            "SELECT n.id, n.post_id, n.mask_id, n.comment_id, n.comment_deleted, "
            "n.content_deleted, n.is_read, n.created_at, "
            "m.token AS mask_token, m.status AS mask_status, "
            "p.title AS post_title, p.status AS post_status "
            "FROM notifications n "
            "LEFT JOIN masks m ON n.mask_id = m.id "
            "LEFT JOIN posts p ON n.post_id = p.id "
            "WHERE " + " AND ".join(where) + " "
            "ORDER BY n.created_at DESC, n.id DESC LIMIT ?"
        )
        params.append(PAGE_SIZE + 1)
        rows = conn.execute(sql, params).fetchall()

        has_more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]

        notifications = [_notification_payload(r) for r in rows]

        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = f"{last['created_at']}:{last['id']}"
    finally:
        conn.close()

    return jsonify(
        {"notifications": notifications, "nextCursor": next_cursor, "unreadCount": unread}
    )


@bp.post("/api/notifications/<int:notification_id>/read")
@auth.login_required
def mark_read(notification_id: int):
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM notifications WHERE id = ? AND user_id = ?",
            (notification_id, g.user["id"]),
        ).fetchone()
        if row is None:
            return _error("NOT_FOUND", "通知不存在", 404)
        conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@bp.post("/api/notifications/read-all")
@auth.login_required
def mark_all_read():
    conn = db.get_connection()
    try:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
            (g.user["id"],),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})
