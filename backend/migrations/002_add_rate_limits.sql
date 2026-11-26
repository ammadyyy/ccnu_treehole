-- 迁移 002：为限速增加上次操作时间字段（按账号计，切换面具不重置）
ALTER TABLE users ADD COLUMN last_post_at TEXT;
ALTER TABLE users ADD COLUMN last_comment_at TEXT;
