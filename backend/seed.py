"""种子数据脚本（T-31）。

幂等可重复执行：
- 超级管理员：复用 admin.create_super_admin（内部已幂等）；
- 账号：按固定邮箱判断，已存在则复用；
- 面具：按每个账号已有面具数判断；
- 帖子/回应：按全表数量阈值判断，不足才补；
- 敏感词：INSERT OR IGNORE（word 唯一）。

用法：python seed.py
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

import config
import db
from admin import create_super_admin

SEED_PASSWORD = "Seed1234"
SUPER_ADMIN_EMAIL = "admin@healing.local"
SUPER_ADMIN_PASSWORD = "Admin1234"
TAGS = ("学业", "情感", "吐槽", "求助", "深夜", "失物", "其他")
MASK_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"
TARGET_POSTS = 60
TARGET_COMMENTS = 200

# 敏感词（预留，供后续待审功能使用）
SENSITIVE_WORDS = ("代考", "代写", "刷单", "兼职刷单", "出售答案", "有偿代课")

# 校园树洞风格标题与正文（随机组合）
TITLES = [
    "期末周真的会谢", "图书馆还有空位吗", "有没有人一起自习", "今天食堂哪个窗口好吃",
    "深夜emo了", "失物招领：校园卡", "求助一道高数题", "吐槽一下选课系统",
    "考研还是就业好纠结", "宿舍楼下有只猫", "跑步搭子有没有", "今天天气不错",
    "实验室招人", "社团招新了解一下", "周末去爬山吗", "最近好焦虑",
    "表白墙的后续呢", "有没有人懂吉他", "考试范围求告知", "失眠怎么办",
]
BODIES = [
    "如题，想听听大家的看法。",
    "最近压力好大，在这里树洞一下。",
    "有没有同样经历的朋友，求建议。",
    "刚经历了一件小事，突然想通了什么。",
    "说出来会好一点，虽然不知道有没有人看。",
    "深夜睡不着，随便写点。",
    "这个点还有人吗，聊两句。",
    "感谢树洞，让我能匿名说这些。",
    "想问一下大家遇到这种情况会怎么办。",
    "突然很怀念以前的日子。",
]
COMMENT_TEXTS = [
    "抱抱你，都会好起来的", "同感，我也是", "可以试试这样……", "加油！",
    "我也有类似的经历", "别想太多，早点休息", "这个我懂，确实难受",
    "楼主说得对", "蹲一个后续", "笑死，太真实了", "谢谢分享", "一起加油",
    "换个角度想也许会好", "你不是一个人", "明天会更好", "顶一下",
]


def _hash(pw: str) -> str:
    return generate_password_hash(pw, method="pbkdf2:sha256")


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _ago(days: int, hours: int = 0) -> str:
    return _iso(datetime.now(timezone.utc) - timedelta(days=days, hours=hours))


def _gen_unique_mask(conn) -> str:
    while True:
        token = "匿名者·" + "".join(random.choice(MASK_CHARS) for _ in range(4))
        if conn.execute("SELECT id FROM masks WHERE token = ?", (token,)).fetchone() is None:
            return token


def seed() -> None:
    config.Config.ensure_dirs()
    db.migrate()

    super_id = create_super_admin(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
    print(f"[seed] 超级管理员 id={super_id}")

    conn = db.get_connection()
    try:
        # 敏感词
        for w in SENSITIVE_WORDS:
            conn.execute("INSERT OR IGNORE INTO sensitive_words(word) VALUES (?)", (w,))

        # 12 个测试账号
        user_ids: list[int] = []
        for i in range(1, 13):
            email = f"seed{i:02d}@test.com"
            row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                user_ids.append(row["id"])
                continue
            cur = conn.execute(
                "INSERT INTO users(email, password_hash, role, status, created_at) VALUES (?,?,?,?,?)",
                (email, _hash(SEED_PASSWORD), "user", "active", _ago(30)),
            )
            user_ids.append(cur.lastrowid)
        print(f"[seed] 测试账号 {len(user_ids)} 个")

        # 每个账号 2–3 个面具
        mask_ids: list[int] = []
        for uid in user_ids:
            existing = conn.execute(
                "SELECT id FROM masks WHERE user_id = ?", (uid,)
            ).fetchall()
            if existing:
                mask_ids.extend(r["id"] for r in existing)
                continue
            n = random.randint(2, 3)
            for _ in range(n):
                cur = conn.execute(
                    "INSERT INTO masks(user_id, token, status, created_at) VALUES (?,?,?,?)",
                    (uid, _gen_unique_mask(conn), "active", _ago(29)),
                )
                mask_ids.append(cur.lastrowid)
        print(f"[seed] 面具 {len(mask_ids)} 个")

        # 60 帖（不足才补）
        existing_posts = conn.execute(
            "SELECT COUNT(*) AS c FROM posts WHERE status = 'published'"
        ).fetchone()["c"]
        post_ids: list[int] = []
        if existing_posts < TARGET_POSTS:
            need = TARGET_POSTS - existing_posts
            for _ in range(need):
                mask_id = random.choice(mask_ids)
                title = random.choice(TITLES)
                body = random.choice(BODIES)
                tag1 = random.choice(TAGS)
                tag2 = random.choice(TAGS) if random.random() < 0.3 else None
                # 时间从 30 天前到现在随机分布
                created = _iso(datetime.now(timezone.utc) - timedelta(
                    days=random.uniform(0, 30), seconds=random.uniform(0, 3600)
                ))
                cur = conn.execute(
                    "INSERT INTO posts(mask_id, title, tag1, tag2, body, status, comment_count, created_at) "
                    "VALUES (?,?,?,?,?,'published',0,?)",
                    (mask_id, title, tag1, tag2, body, created),
                )
                post_ids.append(cur.lastrowid)
        else:
            post_ids = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM posts WHERE status = 'published' LIMIT ?", (TARGET_POSTS,)
                ).fetchall()
            ]
        print(f"[seed] 帖子 {len(post_ids)} 条")

        # 约 200 回应（不足才补）+ 跨账号通知
        existing_comments = conn.execute("SELECT COUNT(*) AS c FROM comments").fetchone()["c"]
        created_comments = 0
        if existing_comments < TARGET_COMMENTS:
            need = TARGET_COMMENTS - existing_comments
            # 帖子 -> 作者账号映射
            post_author = {}
            for pid in post_ids:
                row = conn.execute(
                    "SELECT m.user_id AS uid FROM posts p JOIN masks m ON p.mask_id = m.id "
                    "WHERE p.id = ?",
                    (pid,),
                ).fetchone()
                post_author[pid] = row["uid"] if row else None
            mask_user = {}
            for mid in mask_ids:
                row = conn.execute("SELECT user_id FROM masks WHERE id = ?", (mid,)).fetchone()
                mask_user[mid] = row["user_id"] if row else None

            for _ in range(need):
                pid = random.choice(post_ids)
                # 回应者面具：优先选非作者的面具
                author_uid = post_author[pid]
                candidates = [m for m in mask_ids if mask_user.get(m) != author_uid]
                if not candidates:
                    candidates = mask_ids
                mid = random.choice(candidates)
                body = random.choice(COMMENT_TEXTS)
                created = _iso(datetime.now(timezone.utc) - timedelta(
                    days=random.uniform(0, 29), seconds=random.uniform(0, 3600)
                ))
                cur = conn.execute(
                    "INSERT INTO comments(post_id, mask_id, body, created_at) VALUES (?,?,?,?)",
                    (pid, mid, body, created),
                )
                comment_id = cur.lastrowid
                created_comments += 1

                # 跨账号回应生成通知（模拟真实行为）
                if author_uid is not None and mask_user.get(mid) != author_uid:
                    conn.execute(
                        "INSERT INTO notifications"
                        "(user_id, post_id, mask_id, comment_id, comment_deleted, type, is_read, content_deleted, created_at) "
                        "VALUES (?,?,?,?,0,'post_comment',0,0,?)",
                        (author_uid, pid, mid, comment_id, created),
                    )
                conn.execute(
                    "UPDATE posts SET comment_count = comment_count + 1 WHERE id = ?", (pid,)
                )

        conn.commit()
        print(f"[seed] 回应新增 {created_comments} 条（全表目标 {TARGET_COMMENTS}）")
    finally:
        conn.close()

    print("[seed] 完成")


if __name__ == "__main__":
    seed()
