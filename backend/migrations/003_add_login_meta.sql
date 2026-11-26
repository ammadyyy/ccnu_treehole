-- 迁移 003：登录元信息（供管理员查看面具映射时展示最后登录时间/IP/UA）
ALTER TABLE users ADD COLUMN last_login_at TEXT;
ALTER TABLE users ADD COLUMN last_login_ip TEXT;
ALTER TABLE users ADD COLUMN last_login_ua TEXT;
