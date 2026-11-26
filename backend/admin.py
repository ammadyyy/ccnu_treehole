"""管理员账号体系（T-25）。

- 唯一超级管理员（super_admin）+ 普通管理员（admin）。
- 超级管理员可创建 / 停用 / 恢复 / 重置普通管理员，均需理由并写审计日志。
- 普通管理员不能管理管理员账号。
- 注册接口不能提权，超级管理员只能由初始化脚本或 seed 创建。
"""
from __future__ import annotations

from functools import wraps

from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

import auth
import db
from utils import utcnow

bp = Blueprint("admin_accounts", __name__)

ADMIN_ROLES = ("admin", "super_admin")


def _err(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def admin_required(fn):
    """要求登录且角色为 admin 或 super_admin。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if getattr(g, "user", None) is None or g.user["role"] not in ADMIN_ROLES:
            return _err("FORBIDDEN", "无权限访问", 403)
        return fn(*args, **kwargs)

    return wrapper


def super_admin_required(fn):
    """要求登录且角色为 super_admin。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if getattr(g, "user", None) is None or g.user["role"] != "super_admin":
            return _err("FORBIDDEN", "仅超级管理员可执行此操作", 403)
        return fn(*args, **kwargs)

    return wrapper


def write_audit(conn, actor_id: int, action: str, target_type: str, target_id: int,
                reason: str | None = None, detail: str | None = None) -> None:
    """写入审计日志（只写不改，由调用方在同一事务内 commit）。"""
    conn.execute(
        "INSERT INTO audit_log(actor_user_id, action, target_type, target_id, reason, detail, "
        "actor_ip, source_page, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (actor_id, action, target_type, target_id, reason, detail,
         request.remote_addr, request.referrer or "", utcnow()),
    )


def _admin_payload(row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }


def create_super_admin(email: str, password: str) -> int:
    """创建（或确保存在）唯一超级管理员。供初始化脚本 / seed 使用，不走网页接口。"""
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT id FROM users WHERE role = 'super_admin' LIMIT 1").fetchone()
        if row:
            return row["id"]
        pw_hash = generate_password_hash(password, method="pbkdf2:sha256")
        cur = conn.execute(
            "INSERT INTO users(email, password_hash, role, status, created_at) VALUES (?,?,?,?,?)",
            (email, pw_hash, "super_admin", "active", utcnow()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


@bp.get("/api/admin/admins")
@auth.login_required
@super_admin_required
def list_admins():
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT id, email, role, status, created_at FROM users "
            "WHERE role IN ('admin','super_admin') ORDER BY created_at ASC"
        ).fetchall()
        admins = [_admin_payload(r) for r in rows]
    finally:
        conn.close()
    return jsonify({"admins": admins})


@bp.post("/api/admin/admins")
@auth.login_required
@super_admin_required
def create_admin():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not auth.is_valid_email(email):
        return _err("INVALID_EMAIL", "邮箱格式不正确", 400)
    if not auth.is_valid_password(password):
        return _err("WEAK_PASSWORD", "密码至少 8 位，需同时包含字母和数字", 400)

    conn = db.get_connection()
    try:
        if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            return _err("EMAIL_TAKEN", "该邮箱已注册，请使用未注册邮箱", 409)
        pw_hash = generate_password_hash(password, method="pbkdf2:sha256")
        cur = conn.execute(
            "INSERT INTO users(email, password_hash, role, status, created_at) VALUES (?,?,?,?,?)",
            (email, pw_hash, "admin", "active", utcnow()),
        )
        admin_id = cur.lastrowid
        write_audit(conn, g.user["id"], "create_admin", "user", admin_id,
                    reason=data.get("reason"), detail="创建普通管理员")
        conn.commit()
    finally:
        conn.close()

    return jsonify({"admin": {"id": admin_id, "email": email, "role": "admin", "status": "active"}}), 201


def _change_admin_status(admin_id: int, action: str, new_status: str, reason: str):
    """停用或恢复普通管理员，返回 (response, status) 或 None 表示成功。"""
    if not reason or len(reason.strip()) < 10:
        return _err("REASON_REQUIRED", "请填写至少 10 字的操作理由", 400)

    conn = db.get_connection()
    try:
        target = conn.execute("SELECT * FROM users WHERE id = ?", (admin_id,)).fetchone()
        if target is None:
            return _err("NOT_FOUND", "管理员不存在", 404)
        if target["role"] not in ADMIN_ROLES:
            return _err("NOT_ADMIN", "目标不是管理员账号", 400)
        if target["role"] == "super_admin":
            return _err("FORBIDDEN", "不能操作超级管理员", 400)

        conn.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, admin_id))
        # 停用/恢复后，该管理员全部会话失效（下次请求重新登录校验 status）
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (admin_id,))
        write_audit(conn, g.user["id"], action, "user", admin_id, reason=reason.strip())
        conn.commit()
    finally:
        conn.close()
    return None


@bp.post("/api/admin/admins/<int:admin_id>/disable")
@auth.login_required
@super_admin_required
def disable_admin(admin_id: int):
    data = request.get_json(silent=True) or {}
    err = _change_admin_status(admin_id, "disable_admin", "disabled", data.get("reason") or "")
    return err if err else jsonify({"ok": True})


@bp.post("/api/admin/admins/<int:admin_id>/restore")
@auth.login_required
@super_admin_required
def restore_admin(admin_id: int):
    data = request.get_json(silent=True) or {}
    err = _change_admin_status(admin_id, "restore_admin", "active", data.get("reason") or "")
    return err if err else jsonify({"ok": True})


@bp.post("/api/admin/admins/<int:admin_id>/reset-password")
@auth.login_required
@super_admin_required
def reset_admin_password(admin_id: int):
    data = request.get_json(silent=True) or {}
    new_pw = data.get("password") or ""
    reason = data.get("reason") or ""

    if not auth.is_valid_password(new_pw):
        return _err("WEAK_PASSWORD", "密码至少 8 位，需同时包含字母和数字", 400)
    if not reason or len(reason.strip()) < 10:
        return _err("REASON_REQUIRED", "请填写至少 10 字的操作理由", 400)

    conn = db.get_connection()
    try:
        target = conn.execute("SELECT * FROM users WHERE id = ?", (admin_id,)).fetchone()
        if target is None:
            return _err("NOT_FOUND", "管理员不存在", 404)
        if target["role"] not in ADMIN_ROLES:
            return _err("NOT_ADMIN", "目标不是管理员账号", 400)
        if target["role"] == "super_admin":
            return _err("FORBIDDEN", "不能重置超级管理员密码", 400)

        pw_hash = generate_password_hash(new_pw, method="pbkdf2:sha256")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, admin_id))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (admin_id,))
        write_audit(conn, g.user["id"], "reset_admin_password", "user", admin_id, reason=reason.strip())
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})


@bp.get("/api/admin/audit")
@auth.login_required
@admin_required
def list_audit():
    """审计日志（只读）：普通管理员只看自己，超级管理员看全部；支持时间/操作/管理员筛选。"""
    from datetime import datetime, timedelta, timezone

    action = request.args.get("action") or None
    range_type = request.args.get("range") or "all"   # today | 7d | 30d | all
    actor_id = request.args.get("actor") or None

    conn = db.get_connection()
    try:
        where = []
        params: list = []

        # 权限：普通管理员只能看自己
        if g.user["role"] != "super_admin":
            where.append("a.actor_user_id = ?")
            params.append(g.user["id"])
        elif actor_id:
            where.append("a.actor_user_id = ?")
            params.append(int(actor_id))

        if action:
            where.append("a.action = ?")
            params.append(action)

        # 时间范围
        if range_type in ("today", "7d", "30d"):
            now = datetime.now(timezone.utc)
            if range_type == "today":
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif range_type == "7d":
                start = now - timedelta(days=7)
            else:
                start = now - timedelta(days=30)
            where.append("a.created_at >= ?")
            params.append(start.strftime("%Y-%m-%dT%H:%M:%SZ"))

        sql = (
            "SELECT a.id, a.actor_user_id, a.action, a.target_type, a.target_id, "
            "a.reason, a.detail, a.actor_ip, a.source_page, a.created_at "
            "FROM audit_log a "
            + ("WHERE " + " AND ".join(where) + " " if where else "")
            + "ORDER BY a.created_at DESC, a.id DESC LIMIT 200"
        )
        rows = conn.execute(sql, params).fetchall()
        logs = [
            {
                "id": r["id"],
                "actorUserId": r["actor_user_id"],
                "action": r["action"],
                "targetType": r["target_type"],
                "targetId": r["target_id"],
                "reason": r["reason"],
                "detail": r["detail"],
                "actorIp": r["actor_ip"],
                "sourcePage": r["source_page"],
                "createdAt": r["created_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()

    return jsonify({"logs": logs})


@bp.get("/api/admin/stats")
@auth.login_required
@admin_required
def admin_stats():
    """后台首页统计（30 秒轮询用）：按服务器自然日（UTC）统计今日新增。"""
    from datetime import datetime, timezone

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = db.get_connection()
    try:
        pending_reports = conn.execute(
            "SELECT COUNT(*) AS c FROM reports WHERE status = 'open'"
        ).fetchone()["c"]
        today_reports = conn.execute(
            "SELECT COUNT(*) AS c FROM reports WHERE created_at >= ?", (today_start,)
        ).fetchone()["c"]
        active_users = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE status = 'active'"
        ).fetchone()["c"]
        deleted_users = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE deleted_at IS NOT NULL"
        ).fetchone()["c"]
        total_posts = conn.execute(
            "SELECT COUNT(*) AS c FROM posts WHERE status = 'published'"
        ).fetchone()["c"]
        today_posts = conn.execute(
            "SELECT COUNT(*) AS c FROM posts WHERE status = 'published' AND created_at >= ?",
            (today_start,),
        ).fetchone()["c"]
        today_comments = conn.execute(
            "SELECT COUNT(*) AS c FROM comments WHERE created_at >= ?", (today_start,)
        ).fetchone()["c"]
        deleted_mask_posts = conn.execute(
            "SELECT COUNT(*) AS c FROM posts p "
            "JOIN masks m ON p.mask_id = m.id "
            "JOIN users u ON m.user_id = u.id "
            "WHERE p.status = 'published' AND u.deleted_at IS NOT NULL"
        ).fetchone()["c"]
    finally:
        conn.close()

    return jsonify(
        {
            "pendingReports": pending_reports,
            "todayReports": today_reports,
            "activeUsers": active_users,
            "deletedUsers": deleted_users,
            "totalPosts": total_posts,
            "todayPosts": today_posts,
            "todayComments": today_comments,
            "deletedMaskPosts": deleted_mask_posts,
        }
    )
