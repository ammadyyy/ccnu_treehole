"""账号设置：修改密码、账号注销（T-29 / T-30）。"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

import auth
import db
from utils import utcnow

bp = Blueprint("account", __name__)


def _err(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


@bp.post("/api/me/password")
@auth.login_required
def change_password():
    """修改密码：校验当前密码，更新后保留当前会话、注销其他会话。"""
    data = request.get_json(silent=True) or {}
    current = data.get("currentPassword") or ""
    new_pw = data.get("newPassword") or ""
    confirm = data.get("confirmPassword") or ""

    if not auth.is_valid_password(new_pw):
        return _err("WEAK_PASSWORD", "新密码至少 8 位，需同时包含字母和数字", 400)
    if new_pw != confirm:
        return _err("PASSWORD_MISMATCH", "两次输入的新密码不一致", 400)

    conn = db.get_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], current):
            return _err("BAD_PASSWORD", "当前密码错误", 400)

        new_hash = generate_password_hash(new_pw, method="pbkdf2:sha256")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, g.user["id"]))

        # 保留当前会话，注销该账号在其他设备/浏览器的会话
        token = auth._session_token()
        if token:
            conn.execute(
                "DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
                (g.user["id"], auth._hash_token(token)),
            )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True, "message": "密码修改成功，其他设备已退出登录"})


@bp.post("/api/me/delete")
@auth.login_required
def delete_account():
    """注销账号：校验密码，邮箱置空并快照到 deleted_email，通知与会话删除，历史内容保留。"""
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""

    conn = db.get_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            return _err("BAD_PASSWORD", "密码错误", 400)

        now = utcnow()
        # 释放邮箱：email 置空，原值写入 deleted_email 供管理员查看
        conn.execute(
            "UPDATE users SET email = NULL, deleted_email = ?, status = 'disabled', deleted_at = ? WHERE id = ?",
            (user["email"], now, g.user["id"]),
        )
        # 删除该账号全部通知
        conn.execute("DELETE FROM notifications WHERE user_id = ?", (g.user["id"],))
        # 删除该账号全部会话（含当前会话）
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (g.user["id"],))
        conn.commit()
    finally:
        conn.close()

    resp = jsonify({"ok": True})
    resp.delete_cookie(auth.SESSION_COOKIE, path="/")
    return resp
