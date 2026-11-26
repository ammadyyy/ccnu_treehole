-- 回声洞 初始 schema（迁移 001）
-- 所有时间字段统一保存 UTC ISO-8601 字符串（格式 YYYY-MM-DDTHH:MM:SSZ）
-- 外键由连接层通过 PRAGMA foreign_keys=ON 启用

-- 1. 用户表
CREATE TABLE users (
  id            INTEGER PRIMARY KEY,
  email         TEXT UNIQUE,          -- 当前登录邮箱；注销时置空以释放，SQLite UNIQUE 允许多个 NULL
  deleted_email TEXT,                 -- 注销前邮箱快照，仅管理员可见
  password_hash TEXT NOT NULL,        -- Werkzeug PBKDF2 哈希
  role          TEXT NOT NULL DEFAULT 'user',   -- user | admin | super_admin
  status        TEXT NOT NULL DEFAULT 'active', -- active | disabled
  created_at    TEXT NOT NULL,
  deleted_at    TEXT
);

-- 2. 会话表
CREATE TABLE sessions (
  id              INTEGER PRIMARY KEY,
  user_id         INTEGER NOT NULL REFERENCES users(id),
  token_hash      TEXT NOT NULL,      -- 会话令牌哈希
  current_mask_id INTEGER REFERENCES masks(id),  -- 当前面具；登录为 NULL，选择/切换写入，销毁当前面具时清空
  expires_at      TEXT NOT NULL,
  created_at      TEXT NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(token_hash);

-- 3. 面具表
CREATE TABLE masks (
  id           INTEGER PRIMARY KEY,
  user_id      INTEGER NOT NULL REFERENCES users(id),
  token        TEXT NOT NULL UNIQUE,  -- 显示串「匿名者·k7f2」，全局唯一且永久不复用
  status       TEXT NOT NULL DEFAULT 'active',   -- active | destroyed
  created_at   TEXT NOT NULL,
  destroyed_at TEXT
);
CREATE INDEX idx_masks_user ON masks(user_id, status);

-- 4. 帖子表（作者删除时保留墓碑：id/status/deleted_at，其余字段清空）
CREATE TABLE posts (
  id            INTEGER PRIMARY KEY,
  mask_id       INTEGER REFERENCES masks(id),  -- 墓碑记录可为空
  title         TEXT,                 -- 公开状态必填；墓碑清空
  tag1          TEXT,
  tag2          TEXT,
  body          TEXT,                 -- 正文 1–2000 字符；墓碑清空
  status        TEXT NOT NULL DEFAULT 'published',  -- published | deleted
  deleted_at    TEXT,
  comment_count INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL
);
CREATE INDEX idx_posts_feed ON posts(status, created_at DESC, id DESC);
CREATE INDEX idx_posts_tag  ON posts(status, tag1, created_at DESC);

-- 5. 回应表
CREATE TABLE comments (
  id         INTEGER PRIMARY KEY,
  post_id    INTEGER NOT NULL REFERENCES posts(id),
  mask_id    INTEGER NOT NULL REFERENCES masks(id),
  body       TEXT NOT NULL,           -- 回应正文 1–500 字符
  created_at TEXT NOT NULL
);
CREATE INDEX idx_comments_post ON comments(post_id, created_at, id);

-- 6. 图片表
CREATE TABLE images (
  id          INTEGER PRIMARY KEY,
  post_id     INTEGER NOT NULL REFERENCES posts(id),
  sort_order  INTEGER NOT NULL DEFAULT 0,   -- 相册内顺序
  path        TEXT NOT NULL,                -- 原图相对路径（WebP）
  thumb_path  TEXT NOT NULL,                -- 缩略图相对路径
  bytes       INTEGER NOT NULL,             -- 原图字节数
  thumb_bytes INTEGER NOT NULL,             -- 缩略图字节数
  width       INTEGER NOT NULL,
  height      INTEGER NOT NULL,
  is_animated INTEGER NOT NULL DEFAULT 0,   -- 是否动画图
  caption     TEXT,                         -- 图片说明，可为空，最多 100 字符
  created_at  TEXT NOT NULL
);
CREATE INDEX idx_images_post ON images(post_id, sort_order);

-- 7. 通知表
CREATE TABLE notifications (
  id              INTEGER PRIMARY KEY,
  user_id         INTEGER NOT NULL REFERENCES users(id),   -- 接收通知的账号
  post_id         INTEGER NOT NULL REFERENCES posts(id),   -- 原帖子 ID（关联墓碑）
  mask_id         INTEGER REFERENCES masks(id),            -- 触发回应的面具
  comment_id      INTEGER,                                 -- 触发回应 ID，可为空
  comment_deleted INTEGER NOT NULL DEFAULT 0,              -- 回应是否已删除
  type            TEXT NOT NULL DEFAULT 'post_comment',
  is_read         INTEGER NOT NULL DEFAULT 0,
  content_deleted INTEGER NOT NULL DEFAULT 0,              -- 原内容是否已删除
  created_at      TEXT NOT NULL
);
CREATE INDEX idx_notif_user ON notifications(user_id, is_read, created_at DESC, id DESC);

-- 8. 举报表
CREATE TABLE reports (
  id                      INTEGER PRIMARY KEY,
  target_type             TEXT NOT NULL,    -- post | comment
  target_id               INTEGER NOT NULL,
  reporter_user_id        INTEGER NOT NULL REFERENCES users(id),
  reporter_email_snapshot TEXT NOT NULL,    -- 举报发生时邮箱
  reporter_mask_id        INTEGER REFERENCES masks(id),  -- 举报时使用的面具
  reporter_ip             TEXT NOT NULL,    -- 举报来源完整 IP，永久保留
  reason                  TEXT NOT NULL,    -- 举报原因枚举
  detail                  TEXT,             -- 补充说明，可为空
  status                  TEXT NOT NULL DEFAULT 'open',  -- open | kept | removed
  handled_by              INTEGER REFERENCES users(id),
  handled_reason          TEXT,             -- 管理员处理固定理由
  handled_detail          TEXT,             -- 管理员处理补充说明，至少 10 字
  handled_at              TEXT,
  created_at              TEXT NOT NULL
);
CREATE INDEX idx_reports_target ON reports(target_type, target_id);
CREATE INDEX idx_reports_status ON reports(status, created_at DESC);

-- 9. 举报内部备注表（可多次追加，按创建时间倒序展示，不可改删）
CREATE TABLE report_notes (
  id         INTEGER PRIMARY KEY,
  report_id  INTEGER NOT NULL REFERENCES reports(id),
  admin_id   INTEGER NOT NULL REFERENCES users(id),
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_report_notes ON report_notes(report_id, created_at DESC);

-- 10. 审计日志表（只写不改，不提供删除/导出）
CREATE TABLE audit_log (
  id            INTEGER PRIMARY KEY,
  actor_user_id INTEGER NOT NULL REFERENCES users(id),
  action        TEXT NOT NULL,            -- 删除内容 | 处理举报 | 创建/停用管理员 | 重置密码 | 查看已注销面具映射
  target_type   TEXT,
  target_id     INTEGER,
  reason        TEXT,
  detail        TEXT,
  actor_ip      TEXT,
  source_page   TEXT,
  created_at    TEXT NOT NULL
);
CREATE INDEX idx_audit_actor ON audit_log(actor_user_id, created_at DESC);

-- 11. 敏感词表（预留，敏感词待审功能后续使用）
CREATE TABLE sensitive_words (
  id   INTEGER PRIMARY KEY,
  word TEXT NOT NULL UNIQUE,
  note TEXT
);

-- FTS5 全文检索（trigram 支持中文子串检索）
CREATE VIRTUAL TABLE posts_fts USING fts5(
  title,
  body,
  content='posts',
  content_rowid='id',
  tokenize='trigram'
);

CREATE VIRTUAL TABLE comments_fts USING fts5(
  body,
  content='comments',
  content_rowid='id',
  tokenize='trigram'
);

-- posts FTS 同步触发器
CREATE TRIGGER posts_ai AFTER INSERT ON posts BEGIN
  INSERT INTO posts_fts(rowid, title, body) VALUES (new.id, COALESCE(new.title,''), COALESCE(new.body,''));
END;

CREATE TRIGGER posts_ad AFTER DELETE ON posts BEGIN
  INSERT INTO posts_fts(posts_fts, rowid, title, body) VALUES ('delete', old.id, COALESCE(old.title,''), COALESCE(old.body,''));
END;

CREATE TRIGGER posts_au AFTER UPDATE ON posts BEGIN
  INSERT INTO posts_fts(posts_fts, rowid, title, body) VALUES ('delete', old.id, COALESCE(old.title,''), COALESCE(old.body,''));
  INSERT INTO posts_fts(rowid, title, body) VALUES (new.id, COALESCE(new.title,''), COALESCE(new.body,''));
END;

-- comments FTS 同步触发器
CREATE TRIGGER comments_ai AFTER INSERT ON comments BEGIN
  INSERT INTO comments_fts(rowid, body) VALUES (new.id, new.body);
END;

CREATE TRIGGER comments_ad AFTER DELETE ON comments BEGIN
  INSERT INTO comments_fts(comments_fts, rowid, body) VALUES ('delete', old.id, old.body);
END;

CREATE TRIGGER comments_au AFTER UPDATE ON comments BEGIN
  INSERT INTO comments_fts(comments_fts, rowid, body) VALUES ('delete', old.id, old.body);
  INSERT INTO comments_fts(rowid, body) VALUES (new.id, new.body);
END;
