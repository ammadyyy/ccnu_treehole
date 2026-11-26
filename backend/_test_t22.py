"""T-22 举报提交自测。"""
import tempfile
from pathlib import Path
import config, db

tmp = Path(tempfile.mkdtemp())
config.Config.DATA_DIR = tmp
config.Config.DATABASE_PATH = tmp / "test.db"
config.Config.UPLOAD_DIR = tmp / "uploads"
db.migrate()

from app import app
client = app.test_client()
def j(r): return r.get_json()

# 1. u1 发帖
client.post("/api/auth/register", json={"email": "u1@t.com", "password": "pass1234"})
r = client.post("/api/masks", json={})
m1 = j(r)["mask"]["id"]
client.post("/api/session/current-mask", json={"maskId": m1})
r = client.post("/api/posts", json={"title": "测试帖", "body": "测试正文内容", "tags": ["吐槽"]})
post_id = j(r)["post"]["id"]
print("post:", post_id)

# 2. 游客举报 401
client.post("/api/auth/logout", json={})
r = client.post("/api/reports", json={"targetType": "post", "targetId": post_id, "reason": "辱骂攻击"})
assert r.status_code == 401, f"guest report {r.status_code}"
print("guest 401")

# 3. u1 举报自己内容 400
client.post("/api/auth/login", json={"email": "u1@t.com", "password": "pass1234"})
r = client.post("/api/reports", json={"targetType": "post", "targetId": post_id, "reason": "辱骂攻击"})
assert r.status_code == 400, f"self report {r.status_code}: {j(r)}"
print("self report rejected")

# 4. u2 举报成功
client.post("/api/auth/logout", json={})
client.post("/api/auth/register", json={"email": "u2@t.com", "password": "pass1234"})
r = client.post("/api/masks", json={})
m2 = j(r)["mask"]["id"]
client.post("/api/session/current-mask", json={"maskId": m2})
r = client.post("/api/reports", json={"targetType": "post", "targetId": post_id, "reason": "辱骂攻击", "detail": "这是补充说明"})
assert r.status_code == 201, f"report {r.status_code}: {j(r)}"
print("report ok")

# 5. 限速：再报 2 次（第 2、3 次）成功，第 4 次 429
for i in range(2):
    r = client.post("/api/reports", json={"targetType": "post", "targetId": post_id, "reason": "其他"})
    assert r.status_code == 201, f"report #{i+2} {r.status_code}"
r = client.post("/api/reports", json={"targetType": "post", "targetId": post_id, "reason": "其他"})
assert r.status_code == 429, f"4th report {r.status_code}: {j(r)}"
print("rate limit 429")

# 6. 已删除/不存在目标 404
r = client.post("/api/reports", json={"targetType": "post", "targetId": 99999, "reason": "其他"})
assert r.status_code == 404, f"deleted target {r.status_code}"
print("deleted target 404")

# 7. 无效原因 400
r = client.post("/api/reports", json={"targetType": "post", "targetId": post_id, "reason": "瞎编的原因"})
assert r.status_code == 400, f"invalid reason {r.status_code}"
print("invalid reason 400")

# 8. 校验 reports 表记录了快照字段
conn = db.get_connection()
row = conn.execute("SELECT * FROM reports WHERE target_id = ? LIMIT 1", (post_id,)).fetchone()
conn.close()
assert row["reporter_email_snapshot"] == "u2@t.com"
assert row["reporter_mask_id"] == m2
assert row["reporter_ip"] is not None
print("snapshot fields ok")

print("\nALL T-22 TESTS PASSED")
