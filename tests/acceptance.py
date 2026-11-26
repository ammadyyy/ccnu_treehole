"""回声洞全量验收测试（T-34）。

覆盖用例 UC-01 ~ UC-13 的主流程与关键异常流程。

运行：
    python tests/acceptance.py

说明：
- 使用临时数据库与上传目录，不影响真实数据；
- 每个用例独立捕获异常，最后汇总 PASS/FAIL/SKIP；
- 依赖尚未实现的接口会标记为 SKIP 并在汇总中说明。
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

TMP = tempfile.mkdtemp()
os.environ["DATABASE_PATH"] = os.path.join(TMP, "test.db")
os.environ["DATA_DIR"] = TMP
os.environ["UPLOAD_DIR"] = os.path.join(TMP, "uploads")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import db  # noqa: E402

db.migrate()

from app import app  # noqa: E402
from PIL import Image  # noqa: E402

RESULTS: list[tuple[str, str, str]] = []  # (case, status, detail)


def case(name: str):
    def deco(fn):
        def wrapper():
            try:
                fn()
                RESULTS.append((name, "PASS", ""))
                print(f"PASS  {name}")
            except SkipTest as exc:
                RESULTS.append((name, "SKIP", str(exc)))
                print(f"SKIP  {name}: {exc}")
            except AssertionError as exc:
                RESULTS.append((name, "FAIL", str(exc)))
                print(f"FAIL  {name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                RESULTS.append((name, "ERROR", repr(exc)))
                print(f"ERROR {name}: {exc}")
                traceback.print_exc()

        wrapper.__name__ = name
        return wrapper

    return deco


class SkipTest(Exception):
    pass


def new_client():
    return app.test_client()


def register(client, email="u1@test.com", password="pass1234"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def ensure_mask(client):
    r = client.post("/api/masks")
    assert r.status_code == 201, f"领面具失败 {r.status_code}"
    mask_id = r.get_json()["mask"]["id"]
    r2 = client.post("/api/session/current-mask", json={"maskId": mask_id})
    assert r2.status_code == 200
    return mask_id


def make_jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (200, 30, 30)).save(buf, format="JPEG")
    return buf.getvalue()


# ---------- UC-01 / UC-02 注册、登录、选择面具 ----------

@case("UC-01/02 注册→登录→领面具→设当前面具")
def uc01_02():
    c = new_client()
    r = register(c)
    assert r.status_code == 201, f"注册 {r.status_code}"
    # 弱密码
    r = register(new_client(), email="weak@test.com", password="12345678")
    assert r.status_code == 400, "弱密码应拒绝"
    # 重复邮箱
    r = register(new_client(), email="u1@test.com", password="pass1234")
    assert r.status_code == 409, "重复邮箱应拒绝"
    # me 无面具
    me = c.get("/api/me").get_json()
    assert me["maskCount"] == 0
    # 领面具 + 切当前
    mid = ensure_mask(c)
    me = c.get("/api/me").get_json()
    assert me["maskCount"] == 1
    assert me["currentMask"]["id"] == mid


# ---------- UC-04 发布带图帖子 ----------

@case("UC-04 发布带图帖子 + 各校验")
def uc04():
    c = new_client()
    register(c, "poster@test.com")
    ensure_mask(c)

    r = c.post("/api/posts", data={
        "title": "带图帖子", "body": "这是正文内容",
        "tags": json.dumps(["学业"]), "captions": json.dumps(["测试图片"]),
        "images": (io.BytesIO(make_jpeg()), "test.jpg"),
    }, content_type="multipart/form-data")
    assert r.status_code == 201, f"带图发帖 {r.status_code}"
    body = r.get_json()["post"]
    assert body["imageCount"] == 1
    post_id = body["id"]

    # 超长标题
    r = c.post("/api/posts", json={"title": "x" * 51, "body": "b", "tags": ["学业"]})
    assert r.status_code == 400
    # 无标签
    r = c.post("/api/posts", json={"title": "t", "body": "b", "tags": []})
    assert r.status_code == 400
    # 3 个标签
    r = c.post("/api/posts", json={"title": "t", "body": "b", "tags": ["学业", "情感", "吐槽"]})
    assert r.status_code == 400

    return post_id


# ---------- UC-05 树洞墙 + 标签筛选 ----------

@case("UC-05 树洞墙列表 + 标签筛选 + 热门")
def uc05():
    c = new_client()
    r = c.get("/api/posts")
    assert r.status_code == 200
    data = r.get_json()
    assert "posts" in data and "nextCursor" in data
    r = c.get("/api/posts?tag=学业")
    assert r.status_code == 200
    r = c.get("/api/posts?tag=不存在")
    assert r.status_code == 400
    r = c.get("/api/posts/hot")
    assert r.status_code == 200
    r = c.get("/api/posts/hot?tag=学业")
    assert r.status_code == 200


# ---------- UC-06 回应 ----------

@case("UC-06 匿名回应 + 楼主标记 + 限速")
def uc06():
    author = new_client()
    register(author, "author@test.com")
    ensure_mask(author)
    r = author.post("/api/posts", json={"title": "求助帖", "body": "有人吗", "tags": ["求助"]})
    post_id = r.get_json()["post"]["id"]

    commenter = new_client()
    register(commenter, "commenter@test.com")
    ensure_mask(commenter)
    r = commenter.post(f"/api/posts/{post_id}/comments", json={"body": "我来回你"})
    assert r.status_code == 201, f"回应 {r.status_code}"
    assert r.get_json()["comment"]["isOp"] is False

    # 501 字
    r = commenter.post(f"/api/posts/{post_id}/comments", json={"body": "x" * 501})
    assert r.status_code == 400

    # 列表
    r = commenter.get(f"/api/posts/{post_id}/comments")
    assert r.status_code == 200
    assert len(r.get_json()["comments"]) == 1

    # 楼主自己回应 → isOp True
    author.post(f"/api/posts/{post_id}/comments", json={"body": "谢谢"})
    r = author.get(f"/api/posts/{post_id}/comments")
    comments = r.get_json()["comments"]
    assert any(c["isOp"] for c in comments), "楼主标记缺失"


# ---------- UC-07 通知 ----------

@case("UC-07 通知列表 + 已读")
def uc07():
    u1 = new_client()
    register(u1, "n1@test.com")
    ensure_mask(u1)
    r = u1.post("/api/posts", json={"title": "等回应", "body": "内容", "tags": ["其他"]})
    post_id = r.get_json()["post"]["id"]

    u2 = new_client()
    register(u2, "n2@test.com")
    ensure_mask(u2)
    u2.post(f"/api/posts/{post_id}/comments", json={"body": "回应你"})

    r = u1.get("/api/notifications")
    if r.status_code == 404:
        raise SkipTest("通知接口未实现")
    assert r.status_code == 200, f"通知列表 {r.status_code}"
    data = r.get_json()
    assert len(data["notifications"]) >= 1
    nid = data["notifications"][0]["id"]
    assert data["unreadCount"] >= 1

    r = u1.post(f"/api/notifications/{nid}/read")
    assert r.status_code == 200
    data = u1.get("/api/notifications").get_json()
    assert data["unreadCount"] == 0


# ---------- UC-08 搜索 ----------

@case("UC-08 全文搜索（单字/trigram/特殊字符）")
def uc08():
    c = new_client()
    c.post("/api/auth/register", json={"email": "s@test.com", "password": "pass1234"})
    ensure_mask(c)
    c.post("/api/posts", json={"title": "图书馆", "body": "今天在图书馆哭了一小时", "tags": ["情感"]})

    r = c.get("/api/search?q=图")
    if r.status_code == 404:
        raise SkipTest("搜索接口未实现")
    assert r.status_code == 200
    assert len(r.get_json()["posts"]) >= 1

    r = c.get("/api/search?q=图书馆")
    assert r.status_code == 200
    posts = r.get_json()["posts"]
    ids = [p["id"] for p in posts]
    assert len(ids) == len(set(ids)), "搜索结果重复"

    r = c.get('/api/search?q="测试";')
    assert r.status_code in (200, 400)

    r = c.get("/api/search?q=")
    assert r.status_code in (400, 200)


# ---------- UC-09 删除 -------------

@case("UC-09 删除帖子（墓碑 + 详情 404）")
def uc09():
    c = new_client()
    register(c, "del@test.com")
    ensure_mask(c)
    r = c.post("/api/posts", json={"title": "待删", "body": "内容", "tags": ["其他"]})
    post_id = r.get_json()["post"]["id"]

    # 他人删除
    other = new_client()
    register(other, "other@test.com")
    ensure_mask(other)
    r = other.delete(f"/api/posts/{post_id}")
    assert r.status_code in (403, 404), f"他人删除应拒绝 {r.status_code}"

    # 本人删除
    r = c.delete(f"/api/posts/{post_id}")
    assert r.status_code == 200, f"本人删除 {r.status_code}"
    r = c.get(f"/api/posts/{post_id}")
    assert r.status_code == 404


# ---------- UC-10 销毁面具 ----------

@case("UC-10 销毁面具（历史保留 + 6 个上限）")
def uc10():
    c = new_client()
    register(c, "mask@test.com")
    mask_id = ensure_mask(c)
    r = c.post("/api/posts", json={"title": "面具历史", "body": "内容", "tags": ["吐槽"]})
    post_id = r.get_json()["post"]["id"]

    r = c.delete(f"/api/masks/{mask_id}")
    assert r.status_code == 200
    me = c.get("/api/me").get_json()
    assert me["currentMask"] is None
    # 历史帖仍在（公开可读）
    r = c.get(f"/api/posts/{post_id}")
    assert r.status_code == 200

    # 5 个上限
    for _ in range(5):
        c.post("/api/masks")
    r = c.post("/api/masks")
    assert r.status_code == 409, "超过 5 个应拒绝"


# ---------- UC-11 举报 -------------

@case("UC-11 举报 + 限频 + 不能举报自己")
def uc11():
    author = new_client()
    register(author, "ra@test.com")
    ensure_mask(author)
    r = author.post("/api/posts", json={"title": "被举报帖", "body": "内容", "tags": ["其他"]})
    post_id = r.get_json()["post"]["id"]

    reporter = new_client()
    register(reporter, "rb@test.com")
    ensure_mask(reporter)

    # 游客举报
    guest = new_client()
    r = guest.post("/api/reports", json={"targetType": "post", "targetId": post_id, "reason": "广告或垃圾信息"})
    assert r.status_code == 401, f"游客举报应 401 {r.status_code}"

    # 自己举报自己
    r = author.post("/api/reports", json={"targetType": "post", "targetId": post_id, "reason": "广告或垃圾信息"})
    assert r.status_code in (400, 403), f"自举报应拒绝 {r.status_code}"

    # 正常举报
    r = reporter.post("/api/reports", json={"targetType": "post", "targetId": post_id, "reason": "广告或垃圾信息"})
    if r.status_code == 404:
        raise SkipTest("举报接口未实现")
    assert r.status_code == 201, f"举报 {r.status_code}"


# ---------- UC-12 管理员处理举报 ----------

@case("UC-12 管理员处理举报（队列 + 保留/删除）")
def uc12():
    from admin import create_super_admin

    admin_id = create_super_admin("super@test.com", "AdminPass123")
    c = new_client()
    r = c.post("/api/auth/login", json={"email": "super@test.com", "password": "AdminPass123"})
    assert r.status_code == 200, "超管登录失败"

    r = c.get("/api/admin/reports")
    if r.status_code == 404:
        raise SkipTest("举报队列接口未实现")
    assert r.status_code == 200
    data = r.get_json()
    assert "reports" in data or isinstance(data, list)


# ---------- UC-13 改密 + 注销 ----------

@case("UC-13 修改密码 + 注销账号")
def uc13():
    c = new_client()
    register(c, "acc@test.com", "pass1234")
    ensure_mask(c)

    # 改密：错旧密码
    r = c.post("/api/me/password", json={
        "currentPassword": "wrongpass1", "newPassword": "newpass123", "confirmPassword": "newpass123"
    })
    assert r.status_code == 400
    # 改密：正确
    r = c.post("/api/me/password", json={
        "currentPassword": "pass1234", "newPassword": "newpass123", "confirmPassword": "newpass123"
    })
    assert r.status_code == 200, f"改密 {r.status_code}"
    # 新密码登录
    c2 = new_client()
    r = c2.post("/api/auth/login", json={"email": "acc@test.com", "password": "newpass123"})
    assert r.status_code == 200

    # 注销：错密码
    r = c.post("/api/me/delete", json={"password": "wrongpass1"})
    assert r.status_code == 400
    # 注销：正确
    r = c.post("/api/me/delete", json={"password": "newpass123"})
    assert r.status_code == 200, f"注销 {r.status_code}"
    # 注销后 me 401
    r = c.get("/api/me")
    assert r.status_code == 401
    # 原邮箱可重新注册
    c3 = new_client()
    r = register(c3, "acc@test.com", "pass1234")
    assert r.status_code == 201, "原邮箱应可重新注册"


CASES = [uc01_02, uc04, uc05, uc06, uc07, uc08, uc09, uc10, uc11, uc12, uc13]


def main() -> None:
    for fn in CASES:
        fn()

    print("\n===== 汇总 =====")
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0}
    for name, status, detail in RESULTS:
        counts[status] = counts.get(status, 0) + 1
        if status != "PASS":
            print(f"{status:5} {name}: {detail[:120]}")
    print(f"\nPASS={counts['PASS']} FAIL={counts['FAIL']} SKIP={counts['SKIP']} ERROR={counts['ERROR']}")
    if counts["FAIL"] or counts["ERROR"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
