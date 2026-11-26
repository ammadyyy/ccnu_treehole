// 前端核心类型定义（与后端 posts.py/auth.py/masks.py 返回结构对齐）。

export type Role = 'user' | 'admin' | 'super_admin'

export interface MaskSummary {
  id: number
  token: string
  status: 'active' | 'destroyed'
}

export interface Me {
  id: number
  email: string
  role: Role
  currentMask: MaskSummary | null
  maskCount: number
}

export interface Mask extends MaskSummary {
  createdAt: string
  destroyedAt: string | null
  postCount: number
  commentCount: number
}

// 树洞墙列表卡片（GET /api/posts、/api/posts/hot）
export interface PostCard {
  id: number
  title: string
  excerpt: string
  tags: string[]
  mask: { token: string; status: string }
  commentCount: number
  thumbnail: string | null
  imageCount: number
  createdAt: string
}

export interface PostListResult {
  posts: PostCard[]
  nextCursor: string | null
}

// 帖子详情图片
export interface PostImage {
  sortOrder: number
  path: string
  thumbPath: string
  width: number
  height: number
  isAnimated: boolean
  caption: string | null
}

// 回应
export interface CommentItem {
  id: number
  body: string
  mask: { token: string; status: string }
  isOp: boolean
  createdAt: string
}

// 帖子详情（GET /api/posts/:id）
export interface PostDetail {
  id: number
  title: string
  body: string
  tags: string[]
  mask: { token: string; status: string }
  commentCount: number
  createdAt: string
  images: PostImage[]
  comments: CommentItem[]
}

export interface NotificationItem {
  id: number
  postId: number
  maskToken: string
  maskStatus: string
  postTitle: string | null
  isRead: boolean
  contentDeleted: boolean
  commentDeleted: boolean
  createdAt: string
}

export type TagName = '学业' | '情感' | '吐槽' | '求助' | '深夜' | '失物' | '其他'

export const TAGS: TagName[] = ['学业', '情感', '吐槽', '求助', '深夜', '失物', '其他']

/** 把后端返回的图片相对路径（uploads/...）拼成可访问 URL。 */
export function imageUrl(path: string | null | undefined): string {
  if (!path) return ''
  return `/${path.replace(/^\/+/, '')}`
}
