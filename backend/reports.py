"""举报提交与限频（T-22）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, jsonify, request

import admin
import auth
import config
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


def _target_summary(conn, target_type: str, target_id: int) -> str:
    """返回举报目标的一行摘要，用于队列展示。"""
    if target_type == "post":
        row = conn.execute(
            "SELECT title FROM posts WHERE id = ?", (target_id,)
        ).fetchone()
        return row["title"] if row and row["title"] else "(帖子已删除)"
    row = conn.execute(
        "SELECT body FROM comments WHERE id = ?", (target_id,)
    ).fetchone()
    return (row["body"][:60] + "…") if row and row["body"] else "(回应已删除)"


@bp.get("/api/admin/reports")
@auth.login_required
@admin.admin_required
def list_reports():
    """举报队列：按目标聚合待处理举报，按数量降序（同数按最新时间升序）。"""
    status = request.args.get("status") or "open"     # open | kept | removed
    reason = request.args.get("reason") or None

    conn = db.get_connection()
    try:
        where = ["r.status = ?"]
        params: list = [status]
        if reason:
            where.append(
                "EXISTS (SELECT 1 FROM reports r2 WHERE r2.target_type = r.target_type "
                "AND r2.target_id = r.target_id AND r2.status = ? AND r2.reason = ?)"
            )
            params += [status, reason]

        sql = (
            "SELECT r.target_type, r.target_id, COUNT(*) AS cnt, MAX(r.created_at) AS latest "
            "FROM reports r WHERE " + " AND ".join(where) + " "
            "GROUP BY r.target_type, r.target_id "
            "ORDER BY cnt DESC, latest ASC LIMIT 100"
        )
        rows = conn.execute(sql, params).fetchall()

        items = []
        for r in rows:
            items.append(
                {
                    "targetType": r["target_type"],
                    "targetId": r["target_id"],
                    "count": r["cnt"],
                    "summary": _target_summary(conn, r["target_type"], r["target_id"]),
                    "latestAt": r["latest"],
                }
            )
    finally:
        conn.close()

    return jsonify({"reports": items})


@bp.get("/api/admin/reports/<int:report_id>")
@auth.login_required
@admin.admin_required
def report_detail(report_id: int):
    """举报详情：该目标全部举报记录（旧→新）+ 目标内容 + 内部备注（新→旧）。"""
    conn = db.get_connection()
    try:
        anchor = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if anchor is None:
            return _err("NOT_FOUND", "举报不存在", 404)
        target_type, target_id = anchor["target_type"], anchor["target_id"]

        # 全部举报记录（旧→新）
        rep_rows = conn.execute(
            "SELECT r.id, r.reason, r.detail, r.status, r.reporter_user_id, "
            "r.reporter_email_snapshot, r.reporter_mask_id, r.reporter_ip, "
            "r.handled_reason, r.handled_detail, r.handled_at, r.created_at "
            "FROM reports r WHERE r.target_type = ? AND r.target_id = ? "
            "ORDER BY r.created_at ASC, r.id ASC",
            (target_type, target_id),
        ).fetchall()
        reports = [
            {
                "id": r["id"],
                "reason": r["reason"],
                "detail": r["detail"],
                "status": r["status"],
                "reporterUserId": r["reporter_user_id"],
                "reporterEmail": r["reporter_email_snapshot"],
                "reporterMaskId": r["reporter_mask_id"],
                "reporterIp": r["reporter_ip"],
                "handledReason": r["handled_reason"],
                "handledDetail": r["handled_detail"],
                "handledAt": r["handled_at"],
                "createdAt": r["created_at"],
            }
            for r in rep_rows
        ]

        # 内部备注（新→旧）
        note_rows = conn.execute(
            "SELECT id, admin_id, body, created_at FROM report_notes "
            "WHERE report_id = ? ORDER BY created_at DESC, id DESC",
            (report_id,),
        ).fetchall()
        notes = [
            {"id": n["id"], "adminId": n["admin_id"], "body": n["body"], "createdAt": n["created_at"]}
            for n in note_rows
        ]

        # 目标内容上下文
        context = None
        if target_type == "post":
            p = conn.execute(
                "SELECT p.id, p.title, p.body, p.tag1, p.tag2, p.created_at, m.token AS mask_token "
                "FROM posts p JOIN masks m ON p.mask_id = m.id WHERE p.id = ?",
                (target_id,),
            ).fetchone()
            if p:
                context = {
                    "type": "post",
                    "id": p["id"],
                    "title": p["title"],
                    "body": p["body"],
                    "tags": [t for t in (p["tag1"], p["tag2"]) if t],
                    "maskToken": p["mask_token"],
                    "createdAt": p["created_at"],
                }
        else:
            c = conn.execute(
                "SELECT c.id, c.body, c.created_at, c.post_id, m.token AS mask_token "
                "FROM comments c JOIN masks m ON c.mask_id = m.id WHERE c.id = ?",
                (target_id,),
            ).fetchone()
            if c:
                context = {
                    "type": "comment",
                    "id": c["id"],
                    "body": c["body"],
                    "postId": c["post_id"],
                    "maskToken": c["mask_token"],
                    "createdAt": c["created_at"],
                }
    finally:
        conn.close()

    return jsonify(
        {
            "targetType": target_type,
            "targetId": target_id,
            "reports": reports,
            "notes": notes,
            "context": context,
        }
    )


def _delete_post_files(conn, post_id: int) -> None:
    from pathlib import Path
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


@bp.post("/api/admin/reports/<int:report_id>/resolve")
@auth.login_required
@admin.admin_required
def resolve_report(report_id: int):
    """举报处理与结案：保留或删除；同目标未处理举报统一结案；写审计。"""
    data = request.get_json(silent=True) or {}
    action = data.get("action")            # keep | remove
    reason = data.get("reason") or ""      # 固定理由
    detail = (data.get("detail") or "").strip()

    if action not in ("keep", "remove"):
        return _err("INVALID_ACTION", "处理动作无效", 400)
    if reason not in REPORT_REASONS:
        return _err("INVALID_REASON", "处理理由无效", 400)
    if len(detail) < 10:
        return _err("REASON_REQUIRED", "请填写至少 10 字的处理说明", 400)

    conn = db.get_connection()
    try:
        anchor = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if anchor is None:
            return _err("NOT_FOUND", "举报不存在", 404)
        target_type, target_id = anchor["target_type"], anchor["target_id"]

        # 目标是否已被用户自行删除
        target_deleted = False
        if target_type == "post":
            p = conn.execute("SELECT * FROM posts WHERE id = ?", (target_id,)).fetchone()
            target_deleted = p is None or p["status"] == "deleted"
        else:
            c = conn.execute("SELECT id FROM comments WHERE id = ?", (target_id,)).fetchone()
            target_deleted = c is None

        now = utcnow()
        new_status = "removed" if action == "remove" else "kept"
        # 同目标未处理举报统一结案
        conn.execute(
            "UPDATE reports SET status = ?, handled_by = ?, handled_reason = ?, handled_detail = ?, handled_at = ? "
            "WHERE target_type = ? AND target_id = ? AND status = 'open'",
            (new_status, g.user["id"], reason, detail, now, target_type, target_id),
        )

        if action == "remove" and not target_deleted:
            if target_type == "post":
                _delete_post_files(conn, target_id)
                conn.execute("DELETE FROM comments WHERE post_id = ?", (target_id,))
                conn.execute("DELETE FROM images WHERE post_id = ?", (target_id,))
                conn.execute(
                    "UPDATE posts SET title = NULL, body = NULL, tag1 = NULL, tag2 = NULL, "
                    "mask_id = NULL, status = 'deleted', deleted_at = ? WHERE id = ?",
                    (now, target_id),
                )
                conn.execute(
                    "UPDATE notifications SET content_deleted = 1 WHERE post_id = ?", (target_id,)
                )
                admin.write_audit(conn, g.user["id"], "resolve_report_remove", "post",
                                  target_id, reason=reason, detail=detail)
            else:
                c = conn.execute("SELECT * FROM comments WHERE id = ?", (target_id,)).fetchone()
                if c:
                    conn.execute("DELETE FROM comments WHERE id = ?", (target_id,))
                    conn.execute(
                        "UPDATE posts SET comment_count = MAX(0, comment_count - 1) WHERE id = ?",
                        (c["post_id"],),
                    )
                    conn.execute(
                        "UPDATE notifications SET comment_deleted = 1 WHERE comment_id = ?", (target_id,)
                    )
                admin.write_audit(conn, g.user["id"], "resolve_report_remove", "comment",
                                  target_id, reason=reason, detail=detail)
        elif action == "remove" and target_deleted:
            admin.write_audit(conn, g.user["id"], "resolve_report_remove_already_deleted",
                              target_type, target_id, reason=reason, detail=detail)
        else:
            admin.write_audit(conn, g.user["id"], "resolve_report_keep", target_type,
                              target_id, reason=reason, detail=detail)

        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})


@bp.post("/api/admin/reports/<int:report_id>/notes")
@auth.login_required
@admin.admin_required
def add_report_note(report_id: int):
    """追加内部备注（可多次，不可改删）。"""
    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return _err("INVALID_NOTE", "备注不能为空", 400)

    conn = db.get_connection()
    try:
        anchor = conn.execute("SELECT id FROM reports WHERE id = ?", (report_id,)).fetchone()
        if anchor is None:
            return _err("NOT_FOUND", "举报不存在", 404)
        conn.execute(
            "INSERT INTO report_notes(report_id, admin_id, body, created_at) VALUES (?,?,?,?)",
            (report_id, g.user["id"], body, utcnow()),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True}), 201
