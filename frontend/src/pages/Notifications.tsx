import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import type { NotificationItem, NotificationListResult } from '../lib/types'
import Button from '../components/ui/Button'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EmptyState from '../components/ui/EmptyState'
import Spinner from '../components/ui/Spinner'

function maskLabel(token: string, status: string): string {
  if (status === 'destroyed') return '已销毁面具'
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
  return d.toLocaleDateString('zh-CN')
}

export default function Notifications() {
  const navigate = useNavigate()
  const [items, setItems] = useState<NotificationItem[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [confirmReadAll, setConfirmReadAll] = useState(false)
  const sentinelRef = useRef<HTMLDivElement>(null)

  const load = useCallback(
    async (reset: boolean) => {
      const params = new URLSearchParams()
      if (!reset && cursor) params.set('cursor', cursor)
      const res = await api.get<NotificationListResult>(`/notifications?${params.toString()}`)
      setItems((prev) => (reset ? res.notifications : [...prev, ...res.notifications]))
      setCursor(res.nextCursor)
    },
    [cursor],
  )

  useEffect(() => {
    setLoading(true)
    setError('')
    load(true)
      .catch((e: Error) => setError(e instanceof ApiError ? e.message : '加载失败'))
      .finally(() => setLoading(false))
  }, [load])

  // 滚动加载
  useEffect(() => {
    if (!cursor || loadingMore) return
    const el = sentinelRef.current
    if (!el) return
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setLoadingMore(true)
          load(false)
            .catch(() => {})
            .finally(() => setLoadingMore(false))
        }
      },
      { rootMargin: '200px' },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [cursor, loadingMore, load])

  const markReadLocally = (id: number) => {
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, isRead: true } : n)))
  }

  const onClick = async (n: NotificationItem) => {
    if (!n.isRead) {
      markReadLocally(n.id)
      try {
        await api.post(`/notifications/${n.id}/read`)
        window.dispatchEvent(new Event('notifications-updated'))
      } catch {
        // 已读标记失败不阻断跳转
      }
    }
    if (!n.contentDeleted) {
      navigate(`/post/${n.postId}`)
    }
  }

  const onReadAll = async () => {
    setConfirmReadAll(false)
    try {
      await api.post('/notifications/read-all')
      setItems((prev) => prev.map((n) => ({ ...n, isRead: true })))
      window.dispatchEvent(new Event('notifications-updated'))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '操作失败')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">通知</h1>
        {items.some((n) => !n.isRead) && (
          <Button variant="secondary" onClick={() => setConfirmReadAll(true)}>
            全部标为已读
          </Button>
        )}
      </div>

      {error && <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner size={28} />
        </div>
      ) : items.length === 0 ? (
        <div className="mt-4">
          <EmptyState title="没有通知" description="别人回应你的帖子时会通知你" />
        </div>
      ) : (
        <ul className="mt-4 space-y-2">
          {items.map((n) => {
            const label = n.contentDeleted
              ? '内容已删除'
              : `《${n.postTitle ?? '帖子'}》`
            const suffix = n.commentDeleted ? ' · 回应已删除' : ''
            return (
              <li key={n.id}>
                <button
                  type="button"
                  onClick={() => onClick(n)}
                  disabled={n.contentDeleted}
                  className={`flex w-full items-start gap-2 rounded-lg border bg-white p-3 text-left ${
                    n.contentDeleted ? 'cursor-default border-gray-100' : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {!n.isRead && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-red-500" />}
                  <span className={`flex-1 text-sm ${n.isRead ? 'text-gray-500' : 'text-gray-800'}`}>
                    <span className="font-medium">{maskLabel(n.mask.token, n.mask.status)}</span>
                    {' 回应了你的帖子 '}
                    {label}
                    {suffix}
                    <span className="ml-2 text-xs text-gray-400">{formatTime(n.createdAt)}</span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {cursor && (
        <div ref={sentinelRef} className="flex justify-center py-3">
          {loadingMore ? <Spinner /> : null}
        </div>
      )}

      <ConfirmDialog
        open={confirmReadAll}
        title="全部标为已读"
        message="确定将全部通知标记为已读吗？"
        confirmText="全部已读"
        onConfirm={onReadAll}
        onCancel={() => setConfirmReadAll(false)}
      />
    </div>
  )
}
