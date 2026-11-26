"""帖子发布（T-11）。

- POST /api/posts：标题（1–50，单行）、正文（1–2000）、标签（1–2 个固定标签）。
- 使用当前会话的 current_mask_id（服务端会话为准，不信任前端提交的面具 ID）。
- 账号级 30 秒限速，切换面具不重置计时。
- 图片为 T-12 范畴，本模块先实现纯文字发帖。
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

import auth
import db
from utils import utcnow

bp = Blueprint("posts", __name__)

TAGS = ("学业", "情感", "吐槽", "求助", "深夜", "失物", "其他")
TITLE_MAX = 50
BODY_MAX = 2000
POST_RATE_SECONDS = 30

# 标题单行：不允许换行
_NEWLINE = ("\n", "\r", "\r\n")


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _parse_utc(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


@bp.post("/api/posts")
@auth.login_required
def create_post():
    mask_id = auth.get_current_mask_id()
    if mask_id is None:
        return _error("NO_MASK", "请先选择面具", 400)

    data = request.get_json(silent=True) or {}
    title = data.get("title")
    body = data.get("body")
    tags = data.get("tags")

    # 标题校验（保存时保留原始输入，校验按去除首尾空白后计算）
    if not isinstance(title, str) or not title.strip():
        return _error("INVALID_TITLE", "标题不能为空", 400)
    if any(nl in title for nl in _NEWLINE):
        return _error("INVALID_TITLE", "标题不能包含换行", 400)
    if len(title.strip()) > TITLE_MAX:
        return _error("TITLE_TOO_LONG", f"标题最多 {TITLE_MAX} 字", 400)

    # 正文校验
    if not isinstance(body, str) or not body.strip():
        return _error("INVALID_BODY", "正文不能为空", 400)
    if len(body.strip()) > BODY_MAX:
        return _error("BODY_TOO_LONG", f"正文最多 {BODY_MAX} 字", 400)

    # 标签校验：1–2 个，且都在固定标签内、不重复
    if not isinstance(tags, list) or not (1 <= len(tags) <= 2):
        return _error("INVALID_TAGS", "请选择 1–2 个标签", 400)
    if len(set(tags)) != len(tags):
        return _error("INVALID_TAGS", "标签不能重复", 400)
    for t in tags:
        if t not in TAGS:
            return _error("INVALID_TAGS", f"无效标签：{t}", 400)

    conn = db.get_connection()
    try:
        # 账号级 30 秒限速（跨面具统计该账号最近一次发帖）
        last = conn.execute(
            "SELECT MAX(p.created_at) AS last_at FROM posts p "
            "JOIN masks m ON p.mask_id = m.id "
            "WHERE m.user_id = ? AND p.status = 'published'",
            (g.user["id"],),
        ).fetchone()
        if last and last["last_at"]:
            elapsed = (datetime.now(timezone.utc) - _parse_utc(last["last_at"])).total_seconds()
            if elapsed < POST_RATE_SECONDS:
                wait = int(POST_RATE_SECONDS - elapsed) + 1
                return _error("RATE_LIMITED", f"操作过于频繁，请 {wait} 秒后再试", 429)

        now = utcnow()
        tag1 = tags[0]
        tag2 = tags[1] if len(tags) == 2 else None
        cur = conn.execute(
            "INSERT INTO posts(mask_id, title, tag1, tag2, body, status, comment_count, created_at) "
            "VALUES (?,?,?,?,?,'published',0,?)",
            (mask_id, title, tag1, tag2, body, now),
        )
        conn.commit()
        post_id = cur.lastrowid

        mask = conn.execute(
            "SELECT id, token, status FROM masks WHERE id = ?", (mask_id,)
        ).fetchone()
    finally:
        conn.close()

    return (
        jsonify(
            {
                "post": {
                    "id": post_id,
                    "title": title,
                    "body": body,
                    "tags": tags,
                    "mask": {"id": mask["id"], "token": mask["token"]} if mask else None,
                    "createdAt": now,
                }
            }
        ),
        201,
    )
