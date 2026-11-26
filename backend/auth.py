"""认证与会话（T-05）。

- 邮箱 + 密码注册（无验证码），密码 Werkzeug PBKDF2（pbkdf2:sha256）哈希。
- 服务端会话：Cookie 只存随机 token，会话数据（含 current_mask_id）存 sessions 表。
- httpOnly + SameSite=Lax Cookie；不使用 JWT。
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

import config
import db
from utils import utcnow

bp = Blueprint("auth", __name__)

SESSION_COOKIE = "sid"
SESSION_TTL_DAYS = 7

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _expiry(now_str: str) -> str:
    dt = datetime.strptime(now_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (dt + timedelta(days=SESSION_TTL_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_valid_password(pw: str) -> bool:
    """至少 8 位，且同时包含字母和数字。"""
    return len(pw) >= 8 and any(c.isalpha() for c in pw) and any(c.isdigit() for c in pw)


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def create_session(user_id: int) -> str:
    """创建服务端会话，返回原始 token（仅此一次，随后只存哈希）。"""
    token = secrets.token_urlsafe(32)
    conn = db.get_connection()
    try:
        now = utcnow()
        conn.execute(
            "INSERT INTO sessions(user_id, token_hash, current_mask_id, expires_at, created_at) "
            "VALUES (?,?,?,?,?)",
            (user_id, _hash_token(token), None, _expiry(now), now),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def _session_token() -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def current_session():
    """从 Cookie 读取当前会话行，或 None。"""
    token = _session_token()
    if not token:
        return None
    conn = db.get_connection()
    try:
        return conn.execute(
            "SELECT * FROM sessions WHERE token_hash = ? AND expires_at > ?",
            (_hash_token(token), utcnow()),
        ).fetchone()
    finally:
        conn.close()


def current_user():
    """从 Cookie 解析当前登录用户行（users），或 None。"""
    token = _session_token()
    if not token:
        return None
    conn = db.get_connection()
    try:
        return conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ? AND u.status = 'active'",
            (_hash_token(token), utcnow()),
        ).fetchone()
    finally:
        conn.close()


def get_current_mask_id() -> int | None:
    """返回当前会话的 current_mask_id；无会话或无当前面具时返回 None。

    发帖/回应等写操作一律以服务端会话中的该字段为准，不信任前端提交的面具 ID。
    """
    s = current_session()
    return s["current_mask_id"] if s else None


def set_current_mask(mask_id: int | None) -> None:
    """把当前会话的 current_mask_id 更新为 mask_id（可为 None 表示清空）。"""
    token = _session_token()
    if not token:
        return
    conn = db.get_connection()
    try:
        conn.execute(
            "UPDATE sessions SET current_mask_id = ? WHERE token_hash = ?",
            (mask_id, _hash_token(token)),
        )
        conn.commit()
    finally:
        conn.close()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return _error("UNAUTHORIZED", "请先登录", 401)
        g.user = user
        g.session = current_session()
        return fn(*args, **kwargs)

    return wrapper


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _set_session_cookie(resp, token: str):
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="Lax",
        secure=config.Config.COOKIE_SECURE,
        max_age=SESSION_TTL_DAYS * 86400,
        path="/",
    )
    return resp


def _user_payload(user) -> dict:
    return {"id": user["id"], "email": user["email"], "role": user["role"]}


@bp.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not is_valid_email(email):
        return _error("INVALID_EMAIL", "邮箱格式不正确", 400)
    if not is_valid_password(password):
        return _error("WEAK_PASSWORD", "密码至少 8 位，需同时包含字母和数字", 400)

    conn = db.get_connection()
    try:
        exists = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            return _error("EMAIL_TAKEN", "该邮箱不可用", 409)
        pw_hash = generate_password_hash(password, method="pbkdf2:sha256")
        now = utcnow()
        cur = conn.execute(
            "INSERT INTO users(email, password_hash, role, status, created_at) VALUES (?,?,?,?,?)",
            (email, pw_hash, "user", "active", now),
        )
        conn.commit()
        user_id = cur.lastrowid
    finally:
        conn.close()

    # 注册成功即建立登录态
    token = create_session(user_id)
    resp = jsonify({"ok": True, "user": {"id": user_id, "email": email, "role": "user"}})
    return _set_session_cookie(resp, token), 201


@bp.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    conn = db.get_connection()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND status = 'active'", (email,)
        ).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return _error("BAD_CREDENTIALS", "邮箱或密码错误", 401)

    # 记录最后登录元信息（供管理员查看面具映射）
    conn = db.get_connection()
    try:
        conn.execute(
            "UPDATE users SET last_login_at = ?, last_login_ip = ?, last_login_ua = ? WHERE id = ?",
            (utcnow(), request.remote_addr, request.headers.get("User-Agent", ""), user["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    token = create_session(user["id"])
    resp = jsonify({"ok": True, "user": _user_payload(user)})
    return _set_session_cookie(resp, token)


@bp.post("/api/auth/logout")
def logout():
    token = _session_token()
    if token:
        conn = db.get_connection()
        try:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))
            conn.commit()
        finally:
            conn.close()
    resp = jsonify({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@bp.get("/api/me")
def me():
    user = current_user()
    if user is None:
        return _error("UNAUTHORIZED", "请先登录", 401)

    token = _session_token()
    conn = db.get_connection()
    try:
        s = conn.execute(
            "SELECT current_mask_id FROM sessions WHERE token_hash = ?", (_hash_token(token),)
        ).fetchone()
        current_mask = None
        if s and s["current_mask_id"]:
            m = conn.execute(
                "SELECT id, token, status FROM masks WHERE id = ?", (s["current_mask_id"],)
            ).fetchone()
            if m:
                current_mask = {"id": m["id"], "token": m["token"], "status": m["status"]}
        mask_count = conn.execute(
            "SELECT COUNT(*) AS c FROM masks WHERE user_id = ? AND status = 'active'",
            (user["id"],),
        ).fetchone()["c"]
    finally:
        conn.close()

    return jsonify(
        {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "currentMask": current_mask,  # {id, token, status} 或 None
            "maskCount": mask_count,
        }
    )
