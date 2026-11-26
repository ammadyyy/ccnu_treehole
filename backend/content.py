"""内容管理（T-26）：管理员查看 / 搜索 / 筛选公开内容，删除帖子或回应（理由 + 审计）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, g, jsonify, request

import admin
import auth
import config
import db
from utils import utcnow

bp = Blueprint("content", __name__)

PAGE_SIZE = 20
TAGS = ("学业", "情感", "吐槽", "求助", "深夜", "失物", "其他")


def _err(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _parse_cursor(raw: str | None):
    if not raw:
        return None, None
    parts = raw.split(":")
    if len(parts) == 2:
        return parts[0], int(parts[1])
    return None, None


def _range_start(range_type: str) -> str | None:
    """返回时间范围起点（UTC ISO-8601），None 表示不限。"""
    now = datetime.now(timezone.utc)
    if range_type == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_type == "7d":
        start = now - timedelta(days=7)
    elif range_type == "30d":
        start = now - timedelta(days=30)
    else:
        return None
    return start.strftime("%Y-%m-%dT%H:%M:%SZ")


@bp.get("/api/admin/content")
@auth.login_required
@admin.admin_required
def list_content():
    """管理员内容列表：关键词 + 类型筛选 + 已注销面具筛选 + 时间范围 + 游标分页。"""
    q = (request.args.get("q") or "").strip()
    filter_type = request.args.get("filter") or "all"       # all | posts_only | with_comments
    deleted_mask = request.args.get("deletedMask") == "true"
    range_type = request.args.get("range") or "all"          # today | 7d | 30d | all
    cursor_at, cursor_id = _parse_cursor(request.args.get("cursor"))

    conn = db.get_connection()
    try:
        where = ["p.status = 'published'"]
        params: list = []

        # 关键词：标题或正文子串（参数化 LIKE）
        if q:
            where.append("(p.title LIKE ? OR p.body LIKE ?)")
            like = f"%{q}%"
            params += [like, like]

        # 类型筛选
        if filter_type == "posts_only":
            where.append("p.comment_count = 0")
        elif filter_type == "with_comments":
            where.append("p.comment_count > 0")

        # 已注销面具筛选：帖子作者或任一回应的面具所属账号已注销
        if deleted_mask:
            where.append(
                "(u.deleted_at IS NOT NULL OR EXISTS ("
                "SELECT 1 FROM comments c2 JOIN masks m2 ON c2.mask_id = m2.id "
                "JOIN users u2 ON m2.user_id = u2.id "
                "WHERE c2.post_id = p.id AND u2.deleted_at IS NOT NULL))"
            )

        # 时间范围
        start = _range_start(range_type)
        if start:
            where.append("p.created_at >= ?")
            params.append(start)

        # 游标
        if cursor_at and cursor_id:
            where.append("(p.created_at < ? OR (p.created_at = ? AND p.id < ?))")
            params += [cursor_at, cursor_at, cursor_id]

        sql = (
            "SELECT p.id, p.title, p.body, p.tag1, p.tag2, p.comment_count, p.created_at, "
            "m.token AS mask_token, m.status AS mask_status, "
            "u.deleted_at AS author_deleted_at, "
            "EXISTS (SELECT 1 FROM comments c3 JOIN masks m3 ON c3.mask_id = m3.id "
            "         JOIN users u3 ON m3.user_id = u3.id "
            "         WHERE c3.post_id = p.id AND u3.deleted_at IS NOT NULL) AS has_deleted_comment "
            "FROM posts p JOIN masks m ON p.mask_id = m.id "
            "JOIN users u ON m.user_id = u.id "
            "WHERE " + " AND ".join(where) + " "
            "ORDER BY p.created_at DESC, p.id DESC LIMIT ?"
        )
        params.append(PAGE_SIZE + 1)
        rows = conn.execute(sql, params).fetchall()
        has_more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]

        posts = []
        for r in rows:
            hit = None
            if deleted_mask:
                if r["author_deleted_at"] and r["has_deleted_comment"]:
                    hit = "both"
                elif r["author_deleted_at"]:
                    hit = "author"
                elif r["has_deleted_comment"]:
                    hit = "comment"
            posts.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "body": r["body"],
                    "tags": [t for t in (r["tag1"], r["tag2"]) if t],
                    "mask": {
                        "token": r["mask_token"] if not r["author_deleted_at"] else "已注销面具",
                        "status": r["mask_status"],
                        "deleted": bool(r["author_deleted_at"]),
                    },
                    "commentCount": r["comment_count"],
                    "deletedMaskHit": hit,
                    "createdAt": r["created_at"],
                }
            )

        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = f"{last['created_at']}:{last['id']}"
    finally:
        conn.close()

    return jsonify({"posts": posts, "nextCursor": next_cursor})


def _delete_post_files(conn, post_id: int) -> None:
    rows = conn.execute("SELECT path, thumb_path FROM images WHERE post_id = ?", (post_id,)).fetchall()
    for r in rows:
        for rel in (r["path"], r["thumb_path"]):
            if not rel:
                continue
            p = config.Config.UPLOAD_DIR / rel.replace("uploads/", "", 1)
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass


@bp.post("/api/admin/content/<int:post_id>/delete")
@auth.login_required
@admin.admin_required
def delete_post(post_id: int):
    """管理员删除帖子：理由必填，墓碑保留 id/status/deleted_at，写审计。"""
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if len(reason) < 10:
        return _err("REASON_REQUIRED", "请填写至少 10 字的删除理由", 400)

    conn = db.get_connection()
    try:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if post is None or post["status"] == "deleted":
            return _err("NOT_FOUND", "帖子不存在", 404)

        # 先收集图片路径（事务外删文件）
        _delete_post_files(conn, post_id)

        now = utcnow()
        # 删回应 + 图片记录
        conn.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM images WHERE post_id = ?", (post_id,))
        # 墓碑：清空内容字段，保留 id/status/deleted_at
        conn.execute(
            "UPDATE posts SET title = NULL, body = NULL, tag1 = NULL, tag2 = NULL, "
            "mask_id = NULL, status = 'deleted', deleted_at = ? WHERE id = ?",
            (now, post_id),
        )
        admin.write_audit(conn, g.user["id"], "delete_post", "post", post_id, reason=reason)
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})


@bp.post("/api/admin/comments/<int:comment_id>/delete")
@auth.login_required
@admin.admin_required
def delete_comment(comment_id: int):
    """管理员删除回应：理由必填，减回应数、通知标已删除、写审计。"""
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if len(reason) < 10:
        return _err("REASON_REQUIRED", "请填写至少 10 字的删除理由", 400)

    conn = db.get_connection()
    try:
        c = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if c is None:
            return _err("NOT_FOUND", "回应不存在", 404)

        conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        conn.execute(
            "UPDATE posts SET comment_count = MAX(0, comment_count - 1) WHERE id = ?",
            (c["post_id"],),
        )
        conn.execute(
            "UPDATE notifications SET comment_deleted = 1 WHERE comment_id = ?", (comment_id,)
        )
        admin.write_audit(conn, g.user["id"], "delete_comment", "comment", comment_id, reason=reason)
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})
