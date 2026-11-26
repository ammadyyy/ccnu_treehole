"""面具映射查看（T-27）：管理员查看面具对应的账号信息。

- 普通面具：不记审计日志。
- 已注销面具：记审计日志（含来源页、管理员 IP）。
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify

import admin
import auth
import db

bp = Blueprint("identity", __name__)


def _err(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


@bp.get("/api/admin/masks/<int:mask_id>/identity")
@auth.login_required
@admin.admin_required
def mask_identity(mask_id: int):
    conn = db.get_connection()
    try:
        mask = conn.execute("SELECT * FROM masks WHERE id = ?", (mask_id,)).fetchone()
        if mask is None:
            return _err("NOT_FOUND", "面具不存在", 404)

        user = conn.execute("SELECT * FROM users WHERE id = ?", (mask["user_id"],)).fetchone()
        masks = conn.execute(
            "SELECT id, token, status, created_at, destroyed_at FROM masks "
            "WHERE user_id = ? ORDER BY created_at ASC",
            (mask["user_id"],),
        ).fetchall()

        is_deleted = bool(user["deleted_at"])

        # 已注销面具查看记审计日志；普通面具不记
        if is_deleted:
            admin.write_audit(
                conn, g.user["id"], "view_deleted_mask", "mask", mask_id,
                reason=None, detail="查看已注销面具映射",
            )
            conn.commit()

        email = user["deleted_email"] if is_deleted else user["email"]

        return jsonify(
            {
                "mask": {"id": mask["id"], "token": mask["token"], "status": mask["status"]},
                "account": {
                    "id": user["id"],
                    "email": email,
                    "registeredAt": user["created_at"],
                    "lastLoginAt": user["last_login_at"],
                    "lastLoginIp": user["last_login_ip"],
                    "lastLoginUa": user["last_login_ua"],
                    "deletedAt": user["deleted_at"],
                    "deleted": is_deleted,
                },
                "masks": [
                    {"id": m["id"], "token": m["token"], "status": m["status"],
                     "createdAt": m["created_at"], "destroyedAt": m["destroyed_at"]}
                    for m in masks
                ],
            }
        )
    finally:
        conn.close()
