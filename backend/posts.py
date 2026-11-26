"""帖子发布（T-11）与树洞墙列表（T-13）。

- POST /api/posts：发布帖子（标题/正文/标签/图片）。兼容 JSON（无图）与 multipart（带图）。
- GET  /api/posts：最新列表，created_at + id 游标分页，每页 20 条，支持单标签筛选。
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, jsonify, request, send_from_directory

import auth
import config
import db
import images
from utils import seconds_since, utcnow

bp = Blueprint("posts", __name__)

TAGS = ("学业", "情感", "吐槽", "求助", "深夜", "失物", "其他")
TITLE_MAX = 50
BODY_MAX = 2000
EXCERPT_LEN = 140
PAGE_SIZE = 20
POST_RATE_SECONDS = 30
MAX_IMAGES = 3
CAPTION_MAX = 100

_NEWLINE = ("\n", "\r", "\r\n")


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _validate_title_body(title, body):
    if not isinstance(title, str) or not title.strip():
        return _error("INVALID_TITLE", "标题不能为空", 400)
    if any(nl in title for nl in _NEWLINE):
        return _error("INVALID_TITLE", "标题不能包含换行", 400)
    if len(title.strip()) > TITLE_MAX:
        return _error("TITLE_TOO_LONG", f"标题最多 {TITLE_MAX} 字", 400)
    if not isinstance(body, str) or not body.strip():
        return _error("INVALID_BODY", "正文不能为空", 400)
    if len(body.strip()) > BODY_MAX:
        return _error("BODY_TOO_LONG", f"正文最多 {BODY_MAX} 字", 400)
    return None


def _validate_tags(tags):
    if not isinstance(tags, list) or not (1 <= len(tags) <= 2):
        return _error("INVALID_TAGS", "请选择 1–2 个标签", 400)
    if len(set(tags)) != len(tags):
        return _error("INVALID_TAGS", "标签不能重复", 400)
    for t in tags:
        if t not in TAGS:
            return _error("INVALID_TAGS", f"无效标签：{t}", 400)
    return None


def _validate_caption(caption) -> str | None:
    if caption is None or caption == "":
        return None
    if not isinstance(caption, str):
        return None
    if len(caption) > CAPTION_MAX:
        raise ValueError(f"图片说明最多 {CAPTION_MAX} 字")
    low = caption.lower()
    if any(s in low for s in ("http://", "https://", "www.")):
        raise ValueError("图片说明中不允许填写网址")
    return caption


def _delete_image_files(p) -> None:
    """删除已落盘的原图与缩略图（尽力而为）。"""
    from pathlib import Path
    for rel in (p.path, p.thumb_path):
        if not rel:
            continue
        abs_path = config.Config.UPLOAD_DIR / rel.replace("uploads/", "", 1)
        try:
            Path(abs_path).unlink(missing_ok=True)
        except OSError:
            pass


@bp.post("/api/posts")
@auth.login_required
def create_post():
    mask_id = auth.get_current_mask_id()
    if mask_id is None:
        return _error("NO_MASK", "请先选择面具", 400)

    # 解析请求：multipart（带图）或 JSON（纯文字，兼容 T-11）
    files: list = []
    captions: list = []
    if request.is_json:
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        body = data.get("body")
        tags = data.get("tags")
    else:
        title = request.form.get("title")
        body = request.form.get("body")
        tags_raw = request.form.get("tags")
        try:
            tags = json.loads(tags_raw) if tags_raw else []
        except json.JSONDecodeError:
            return _error("INVALID_TAGS", "标签格式错误", 400)
        files = request.files.getlist("images")
        captions_raw = request.form.get("captions")
        try:
            captions = json.loads(captions_raw) if captions_raw else []
        except json.JSONDecodeError:
            return _error("INVALID_CAPTION", "图片说明格式错误", 400)

    err = _validate_title_body(title, body)
    if err:
        return err
    err = _validate_tags(tags)
    if err:
        return err

    if len(files) > MAX_IMAGES:
        return _error("TOO_MANY_IMAGES", f"最多上传 {MAX_IMAGES} 张图片", 400)

    # 处理图片（失败时清理已落盘文件）
    processed: list = []
    try:
        for idx, f in enumerate(files):
            raw = f.read()
            cap = captions[idx] if idx < len(captions) else None
            try:
                caption = _validate_caption(cap)
            except ValueError as exc:
                raise images.ImageError(str(exc)) from exc
            p = images.process_image(raw)
            processed.append((p, caption))
    except images.ImageError as exc:
        for p, _cap in processed:
            _delete_image_files(p)
        return _error("IMAGE_INVALID", str(exc), 400)

    conn = db.get_connection()
    try:
        # 账号级 30 秒限速（记录在 users.last_post_at，切换面具不重置）
        row = conn.execute("SELECT last_post_at FROM users WHERE id = ?", (g.user["id"],)).fetchone()
        elapsed = seconds_since(row["last_post_at"]) if row and row["last_post_at"] else None
        if elapsed is not None and elapsed < POST_RATE_SECONDS:
            for p, _cap in processed:
                _delete_image_files(p)
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
        post_id = cur.lastrowid
        conn.execute("UPDATE users SET last_post_at = ? WHERE id = ?", (now, g.user["id"]))

        for i, (p, caption) in enumerate(processed):
            conn.execute(
                "INSERT INTO images(post_id, sort_order, path, thumb_path, bytes, thumb_bytes, "
                "width, height, is_animated, caption, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    post_id, i, p.path, p.thumb_path, p.bytes, p.thumb_bytes,
                    p.width, p.height, int(p.is_animated), caption, now,
                ),
            )
        conn.commit()

        mask = conn.execute("SELECT id, token, status FROM masks WHERE id = ?", (mask_id,)).fetchone()
    except Exception:  # noqa: BLE001
        for p, _cap in processed:
            _delete_image_files(p)
        conn.rollback()
        raise
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
                    "imageCount": len(processed),
                    "createdAt": now,
                }
            }
        ),
        201,
    )


@bp.get("/api/posts")
def list_posts():
    tag = request.args.get("tag") or None
    if tag is not None and tag not in TAGS:
        return _error("INVALID_TAG", "无效标签", 400)

    cursor = request.args.get("cursor") or None
    cursor_at = cursor_id = None
    if cursor:
        parts = cursor.split(":")
        if len(parts) == 2:
            cursor_at, cursor_id = parts[0], int(parts[1])

    conn = db.get_connection()
    try:
        where = ["p.status = 'published'"]
        params: list = []
        if tag:
            where.append("(p.tag1 = ? OR p.tag2 = ?)")
            params += [tag, tag]
        if cursor_at and cursor_id:
            where.append("(p.created_at < ? OR (p.created_at = ? AND p.id < ?))")
            params += [cursor_at, cursor_at, cursor_id]

        sql = (
            "SELECT p.id, p.title, p.body, p.tag1, p.tag2, p.comment_count, p.created_at, "
            "m.token AS mask_token, m.status AS mask_status "
            "FROM posts p JOIN masks m ON p.mask_id = m.id "
            "WHERE " + " AND ".join(where) + " "
            "ORDER BY p.created_at DESC, p.id DESC LIMIT ?"
        )
        params.append(PAGE_SIZE + 1)
        rows = conn.execute(sql, params).fetchall()

        has_more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]

        post_ids = [r["id"] for r in rows]
        thumbs: dict = {}
        counts: dict = {}
        if post_ids:
            q = ",".join("?" for _ in post_ids)
            for r in conn.execute(
                f"SELECT post_id, thumb_path FROM images WHERE post_id IN ({q}) AND sort_order = 0",
                post_ids,
            ).fetchall():
                thumbs[r["post_id"]] = r["thumb_path"]
            for r in conn.execute(
                f"SELECT post_id, COUNT(*) AS c FROM images WHERE post_id IN ({q}) GROUP BY post_id",
                post_ids,
            ).fetchall():
                counts[r["post_id"]] = r["c"]

        posts = []
        for r in rows:
            body = r["body"] or ""
            excerpt = body[:EXCERPT_LEN] + ("…" if len(body) > EXCERPT_LEN else "")
            tags = [t for t in (r["tag1"], r["tag2"]) if t]
            posts.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "excerpt": excerpt,
                    "tags": tags,
                    "mask": {
                        "token": r["mask_token"],
                        "status": r["mask_status"],
                    },
                    "commentCount": r["comment_count"],
                    "thumbnail": thumbs.get(r["id"]),
                    "imageCount": counts.get(r["id"], 0),
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


@bp.get("/api/posts/<int:post_id>")
def get_post(post_id: int):
    """帖子详情（T-15）：返回完整帖子 + 图片（含 sortOrder/caption）+ 回应列表。

    公开接口，不暴露账号邮箱或其他面具关系。
    """
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT p.*, m.token AS mask_token, m.status AS mask_status "
            "FROM posts p JOIN masks m ON p.mask_id = m.id "
            "WHERE p.id = ? AND p.status = 'published'",
            (post_id,),
        ).fetchone()
        if row is None:
            return _error("NOT_FOUND", "帖子不存在", 404)

        post_mask_id = row["mask_id"]

        img_rows = conn.execute(
            "SELECT sort_order, path, thumb_path, width, height, is_animated, caption "
            "FROM images WHERE post_id = ? ORDER BY sort_order ASC",
            (post_id,),
        ).fetchall()
        images_list = [
            {
                "sortOrder": r["sort_order"],
                "path": r["path"],
                "thumbPath": r["thumb_path"],
                "width": r["width"],
                "height": r["height"],
                "isAnimated": bool(r["is_animated"]),
                "caption": r["caption"],
            }
            for r in img_rows
        ]

        # 回应按时间正序；仅发帖面具回应标「楼主」
        comment_rows = conn.execute(
            "SELECT c.id, c.mask_id, c.body, c.created_at, m.token AS mask_token, m.status AS mask_status "
            "FROM comments c JOIN masks m ON c.mask_id = m.id "
            "WHERE c.post_id = ? ORDER BY c.created_at ASC, c.id ASC",
            (post_id,),
        ).fetchall()
        comments_list = [
            {
                "id": r["id"],
                "body": r["body"],
                "mask": {"token": r["mask_token"], "status": r["mask_status"]},
                "isOp": bool(r["mask_id"] == post_mask_id),
                "createdAt": r["created_at"],
            }
            for r in comment_rows
        ]
    finally:
        conn.close()

    return jsonify(
        {
            "post": {
                "id": row["id"],
                "title": row["title"],
                "body": row["body"],
                "tags": [t for t in (row["tag1"], row["tag2"]) if t],
                "mask": {"token": row["mask_token"], "status": row["mask_status"]},
                "commentCount": row["comment_count"],
                "createdAt": row["created_at"],
                "images": images_list,
                "comments": comments_list,
            }
        }
    )


@bp.get("/uploads/<path:filename>")
def serve_upload(filename: str):
    """服务已上传图片（原图与缩略图）。"""
    return send_from_directory(config.Config.UPLOAD_DIR, filename)


# ---------------------------------------------------------------------------
# T-14 24 小时热门与缓存
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

HOT_CACHE_TTL = 300   # 5 分钟
HOT_LIMIT = 20
_hot_lock = threading.Lock()
_hot_cache: dict = {}  # key -> {"data": [...], "expires_at": float, "refreshing": bool}


def _hot_key(tag: str | None) -> str:
    return tag or "__all__"


def _compute_hot(tag: str | None) -> list:
    """计算热门前 20：最近 24h 公开回应数降序，同数按发布时间倒序。"""
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = db.get_connection()
    try:
        where = ["p.status = 'published'"]
        params: list = [since]
        if tag:
            where.append("(p.tag1 = ? OR p.tag2 = ?)")
            params += [tag, tag]

        sql = (
            "SELECT p.id, p.title, p.body, p.tag1, p.tag2, p.comment_count, p.created_at, "
            "m.token AS mask_token, m.status AS mask_status, "
            "(SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id AND c.created_at >= ?) AS hot_count "
            "FROM posts p JOIN masks m ON p.mask_id = m.id "
            "WHERE " + " AND ".join(where) + " "
            "ORDER BY hot_count DESC, p.created_at DESC, p.id DESC LIMIT ?"
        )
        params.append(HOT_LIMIT)
        rows = conn.execute(sql, params).fetchall()

        post_ids = [r["id"] for r in rows]
        thumbs: dict = {}
        counts: dict = {}
        if post_ids:
            q = ",".join("?" for _ in post_ids)
            for r in conn.execute(
                f"SELECT post_id, thumb_path FROM images WHERE post_id IN ({q}) AND sort_order = 0",
                post_ids,
            ).fetchall():
                thumbs[r["post_id"]] = r["thumb_path"]
            for r in conn.execute(
                f"SELECT post_id, COUNT(*) AS c FROM images WHERE post_id IN ({q}) GROUP BY post_id",
                post_ids,
            ).fetchall():
                counts[r["post_id"]] = r["c"]

        cards = []
        for r in rows:
            body = r["body"] or ""
            excerpt = body[:EXCERPT_LEN] + ("…" if len(body) > EXCERPT_LEN else "")
            tags = [t for t in (r["tag1"], r["tag2"]) if t]
            cards.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "excerpt": excerpt,
                    "tags": tags,
                    "mask": {"token": r["mask_token"], "status": r["mask_status"]},
                    "commentCount": r["comment_count"],
                    "thumbnail": thumbs.get(r["id"]),
                    "imageCount": counts.get(r["id"], 0),
                    "createdAt": r["created_at"],
                }
            )
        return cards
    finally:
        conn.close()


def _refresh_hot(key: str, tag: str | None) -> None:
    """后台刷新热门缓存；失败保留旧值并记日志。"""
    try:
        data = _compute_hot(tag)
        with _hot_lock:
            _hot_cache[key] = {"data": data, "expires_at": time.time() + HOT_CACHE_TTL, "refreshing": False}
    except Exception:  # noqa: BLE001
        logger.exception("热门缓存刷新失败: %s", key)
        with _hot_lock:
            entry = _hot_cache.get(key)
            if entry:
                entry["refreshing"] = False  # 保留旧值


def _get_hot(tag: str | None) -> list:
    key = _hot_key(tag)
    with _hot_lock:
        entry = _hot_cache.get(key)
        now = time.time()
        if entry and entry["data"] is not None:
            if now < entry["expires_at"]:
                return entry["data"]  # 未过期
            if not entry["refreshing"]:
                # 过期但仍有旧值：先返旧值，后台刷新
                entry["refreshing"] = True
                threading.Thread(target=_refresh_hot, args=(key, tag), daemon=True).start()
            return entry["data"]

    # 冷启动：同步计算
    data = _compute_hot(tag)
    with _hot_lock:
        _hot_cache[key] = {"data": data, "expires_at": time.time() + HOT_CACHE_TTL, "refreshing": False}
    return data


@bp.get("/api/posts/hot")
def hot_posts():
    tag = request.args.get("tag") or None
    if tag is not None and tag not in TAGS:
        return _error("INVALID_TAG", "无效标签", 400)
    data = _get_hot(tag)
    return jsonify({"posts": data, "nextCursor": None})
