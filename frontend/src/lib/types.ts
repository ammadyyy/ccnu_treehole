// 前端核心类型定义（对应规格第 6 章数据模型，字段名以后端实际返回为准）。

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

export interface PostImage {
  id: number
  sortOrder: number
  url: string
  thumbUrl: string
  width: number
  height: number
  isAnimated: boolean
  caption: string | null
}

export interface Post {
  id: number
  maskToken: string
  maskStatus: 'active' | 'destroyed' | 'deleted'
  title: string
  tag1: string
  tag2: string | null
  body: string
  commentCount: number
  createdAt: string
  images: PostImage[]
  isAuthor: boolean
}

export interface CommentItem {
  id: number
  maskToken: string
  maskStatus: 'active' | 'destroyed' | 'deleted'
  body: string
  createdAt: string
  isAuthor: boolean
  isOp: boolean
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

export interface Page<T> {
  items: T[]
  nextCursor: string | null
}

export type TagName = '学业' | '情感' | '吐槽' | '求助' | '深夜' | '失物' | '其他'

export const TAGS: TagName[] = ['学业', '情感', '吐槽', '求助', '深夜', '失物', '其他']
