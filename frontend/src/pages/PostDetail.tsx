import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { imageUrl, type CommentItem, type PostDetail as PostDetailType } from '../lib/types'
import Button from '../components/ui/Button'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EmptyState from '../components/ui/EmptyState'
import Modal from '../components/ui/Modal'
import Spinner from '../components/ui/Spinner'

function maskLabel(token: string, status: string): string {
  if (status === 'destroyed') return `${token} · 已销毁面具`
  if (status === 'deleted') return '已注销面具'
  return token
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const diff = Date.now() - d.getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day} 天前`
  return d.toLocaleString('zh-CN')
}

export default function PostDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [post, setPost] = useState<PostDetailType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // 相册
  const [imgIndex, setImgIndex] = useState(0)
  const [lightboxOpen, setLightboxOpen] = useState(false)
  const touchStartX = useRef<number | null>(null)

  // 回应
  const [comments, setComments] = useState<CommentItem[]>([])
  const [commentCursor, setCommentCursor] = useState<string | null>(null)
  const [commentsLoadingMore, setCommentsLoadingMore] = useState(false)
  const [newComment, setNewComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [confirmDeleteComment, setConfirmDeleteComment] = useState<CommentItem | null>(null)
  const [isAuthor, setIsAuthor] = useState(false)
  const [confirmDeletePost, setConfirmDeletePost] = useState(false)
  const commentSentinelRef = useRef<HTMLDivElement>(null)
  const commentListRef = useRef<HTMLUListElement>(null)

  const loadPost = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get<{ post: PostDetailType }>(`/posts/${id}`)
      setPost(res.post)
      // 判断作者：当前账号是否拥有该帖的面具（用面具列表对比 token）
      try {
        const m = await api.get<{ masks: { token: string }[] }>('/masks')
        setIsAuthor(m.masks.some((x) => x.token === res.post.mask.token))
      } catch {
        setIsAuthor(false)
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [id])

  const loadComments = useCallback(
    async (reset: boolean) => {
      const params = new URLSearchParams()
      if (!reset && commentCursor) params.set('cursor', commentCursor)
      const res = await api.get<{ comments: CommentItem[]; nextCursor: string | null }>(
        `/posts/${id}/comments?${params.toString()}`,
      )
      setComments((prev) => (reset ? res.comments : [...prev, ...res.comments]))
      setCommentCursor(res.nextCursor)
    },
    [id, commentCursor],
  )

  useEffect(() => {
    void loadPost()
    void loadComments(true).catch(() => {})
  }, [loadPost, loadComments])

  // 回应滚动加载
  useEffect(() => {
    if (!commentCursor) return
    const el = commentSentinelRef.current
    if (!el) return
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !commentsLoadingMore) {
          setCommentsLoadingMore(true)
          loadComments(false)
            .catch(() => {})
            .finally(() => setCommentsLoadingMore(false))
        }
      },
      { rootMargin: '200px' },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [commentCursor, commentsLoadingMore, loadComments])

  // 相册键盘切换
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!post || post.images.length <= 1) return
      if (e.key === 'ArrowLeft') setImgIndex((i) => (i - 1 + post.images.length) % post.images.length)
      if (e.key === 'ArrowRight') setImgIndex((i) => (i + 1) % post.images.length)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [post])

  const onSubmitComment = async () => {
    if (!newComment.trim()) return
    setSubmitting(true)
    setError('')
    try {
      await api.post(`/posts/${id}/comments`, { body: newComment.trim() })
      setNewComment('')
      // 重新加载回应（从最早开始，简单起见重置）
      await loadComments(true)
      // 定位到列表末尾
      requestAnimationFrame(() => {
        commentListRef.current?.scrollIntoView({ block: 'end' })
      })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '回应失败')
    } finally {
      setSubmitting(false)
    }
  }

  const onDeleteComment = async () => {
    if (!confirmDeleteComment) return
    try {
      await api.del(`/comments/${confirmDeleteComment.id}`)
      setConfirmDeleteComment(null)
      setComments((prev) => prev.filter((c) => c.id !== confirmDeleteComment.id))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '删除失败')
    }
  }

  const onDeletePost = async () => {
    setConfirmDeletePost(false)
    try {
      await api.del(`/posts/${id}`)
      navigate('/')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '删除失败')
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size={28} />
      </div>
    )
  }

  if (!post) {
    return <EmptyState title="帖子不存在" description="它可能已被删除" />
  }

  const images = post.images
  const canComment = !!user?.currentMask
  const isMyComment = (c: CommentItem) =>
    user?.currentMask && c.mask.token === user.currentMask.token

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-900">{post.title}</h1>

      {/* 横向相册（图片在正文上方） */}
      {images.length > 0 && (
        <div
          className="relative mt-4 overflow-hidden rounded-lg bg-gray-100"
          onTouchStart={(e) => (touchStartX.current = e.touches[0].clientX)}
          onTouchEnd={(e) => {
            if (touchStartX.current === null) return
            const dx = e.changedTouches[0].clientX - touchStartX.current
            touchStartX.current = null
            if (Math.abs(dx) > 40) {
              setImgIndex((i) => (i + (dx < 0 ? 1 : -1) + images.length) % images.length)
            }
          }}
        >
          <button
            type="button"
            onClick={() => setLightboxOpen(true)}
            className="flex w-full items-center justify-center"
            style={{ maxHeight: '60vh' }}
          >
            <img
              src={imageUrl(images[imgIndex].path)}
              alt={images[imgIndex].caption ?? `帖子图片 ${imgIndex + 1}`}
              className="max-h-[60vh] w-full object-contain"
            />
          </button>
          {images.length > 1 && (
            <>
              <button
                type="button"
                onClick={() => setImgIndex((i) => (i - 1 + images.length) % images.length)}
                className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-black/40 px-2 py-1 text-white hover:bg-black/60"
                aria-label="上一张"
              >
                ‹
              </button>
              <button
                type="button"
                onClick={() => setImgIndex((i) => (i + 1) % images.length)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-black/40 px-2 py-1 text-white hover:bg-black/60"
                aria-label="下一张"
              >
                ›
              </button>
              <span className="absolute bottom-2 right-2 rounded bg-black/50 px-1.5 py-0.5 text-xs text-white">
                {imgIndex + 1} / {images.length}
              </span>
            </>
          )}
        </div>
      )}

      {/* 正文 */}
      <p className="preserve-text mt-4 text-gray-800">{post.body}</p>

      {/* 元信息 */}
      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-400">
        <span>{maskLabel(post.mask.token, post.mask.status)}</span>
        {post.tags.map((t) => (
          <span key={t} className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-500">
            {t}
          </span>
        ))}
        <span>{formatTime(post.createdAt)}</span>
      </div>

      {error && <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {/* 回应区 */}
      <div className="mt-6 border-t border-gray-200 pt-4">
        <h2 className="text-sm font-medium text-gray-500">回应 {post.commentCount}</h2>

        {comments.length === 0 ? (
          <div className="mt-3">
            <EmptyState title="还没有回应" description="来说点什么吧" />
          </div>
        ) : (
          <ul ref={commentListRef} className="mt-3 space-y-3">
            {comments.map((c) => (
              <li key={c.id} className="rounded-lg border border-gray-100 bg-white p-3">
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>
                    {maskLabel(c.mask.token, c.mask.status)}
                    {c.isOp && (
                      <span className="ml-2 rounded bg-gray-900 px-1 py-0.5 text-white">楼主</span>
                    )}
                  </span>
                  <span>{formatTime(c.createdAt)}</span>
                </div>
                <p className="preserve-text mt-1 text-sm text-gray-800">{c.body}</p>
                {isMyComment(c) && (
                  <button
                    type="button"
                    onClick={() => setConfirmDeleteComment(c)}
                    className="mt-1 text-xs text-gray-400 hover:text-red-600"
                  >
                    删除
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {commentCursor && (
          <div ref={commentSentinelRef} className="flex justify-center py-3">
            {commentsLoadingMore ? <Spinner /> : null}
          </div>
        )}

        {/* 回应输入 */}
        {canComment ? (
          <div className="mt-4">
            <textarea
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder={`以「${user!.currentMask!.token}」回应…`}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
            />
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xs text-gray-400">{newComment.length}/500</span>
              <Button onClick={onSubmitComment} loading={submitting} disabled={submitting || !newComment.trim()}>
                回应
              </Button>
            </div>
          </div>
        ) : (
          <p className="mt-4 text-sm text-gray-400">登录并选择面具后才能回应</p>
        )}
      </div>

      {/* 大图预览 */}
      <Modal open={lightboxOpen} onClose={() => setLightboxOpen(false)} closeOnOverlay={false}>
        <div className="relative bg-black">
          <img
            src={imageUrl(images[imgIndex]?.path)}
            alt={images[imgIndex]?.caption ?? '大图预览'}
            className="max-h-[85vh] w-full object-contain"
          />
          {images[imgIndex]?.caption && (
            <p className="bg-black/80 px-4 py-2 text-center text-sm text-white">
              {images[imgIndex].caption}
            </p>
          )}
          <button
            type="button"
            onClick={() => setLightboxOpen(false)}
            className="absolute right-2 top-2 rounded-full bg-black/50 px-2 py-1 text-white hover:bg-black/70"
            aria-label="关闭"
          >
            ✕
          </button>
        </div>
      </Modal>

      <ConfirmDialog
        open={confirmDeleteComment !== null}
        title="删除回应"
        message="删除后不可恢复，确定删除这条回应吗？"
        confirmText="删除"
        danger
        onConfirm={onDeleteComment}
        onCancel={() => setConfirmDeleteComment(null)}
      />
    </div>
  )
}
