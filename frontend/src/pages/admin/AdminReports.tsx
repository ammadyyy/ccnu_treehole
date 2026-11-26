import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import EmptyState from '../../components/ui/EmptyState'
import Spinner from '../../components/ui/Spinner'

interface ReportQueueItem {
  targetType: 'post' | 'comment'
  targetId: number
  anchorId: number
  count: number
  summary: string
  latestAt: string
}

const REASONS = ['广告或垃圾信息', '辱骂攻击', '色情低俗', '泄露隐私', '违法违规', '其他']

export default function AdminReports() {
  const [items, setItems] = useState<ReportQueueItem[]>([])
  const [status, setStatus] = useState('open')
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const params = new URLSearchParams({ status })
    if (reason) params.set('reason', reason)
    try {
      const res = await api.get<{ reports: ReportQueueItem[] }>(`/admin/reports?${params.toString()}`)
      setItems(res.reports)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [status, reason])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-900">举报队列</h1>

      <div className="mt-4 flex flex-wrap gap-2">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
        >
          <option value="open">待处理</option>
          <option value="kept">已保留</option>
          <option value="removed">已删除</option>
        </select>
        <select
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
        >
          <option value="">全部原因</option>
          {REASONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner size={28} />
        </div>
      ) : items.length === 0 ? (
        <div className="mt-4">
          <EmptyState title="没有举报" />
        </div>
      ) : (
        <ul className="mt-4 space-y-2">
          {items.map((it) => (
            <li key={`${it.targetType}-${it.targetId}`}>
              <Link
                to={`/admin/reports/${it.anchorId}`}
                className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 hover:border-gray-300"
              >
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-900">
                    {it.targetType === 'post' ? '帖子' : '回应'} · {it.summary}
                  </div>
                  <div className="mt-1 text-xs text-gray-400">
                    {it.count} 条举报 · 最新 {it.latestAt}
                  </div>
                </div>
                <span className="ml-3 rounded bg-red-50 px-2 py-1 text-xs text-red-600">
                  {it.count}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
