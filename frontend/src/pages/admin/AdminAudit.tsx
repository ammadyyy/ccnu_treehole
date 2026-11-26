import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../lib/api'
import EmptyState from '../../components/ui/EmptyState'
import Spinner from '../../components/ui/Spinner'

interface AuditLog {
  id: number
  actorUserId: number
  action: string
  targetType: string
  targetId: number
  reason: string | null
  detail: string | null
  actorIp: string
  sourcePage: string
  createdAt: string
}

const ACTION_LABELS: Record<string, string> = {
  resolve_report_remove: '删除内容（举报）',
  resolve_report_remove_already_deleted: '删除内容（已删除）',
  resolve_report_keep: '保留内容（举报）',
  create_admin: '创建管理员',
  disable_admin: '停用管理员',
  restore_admin: '恢复管理员',
  reset_admin_password: '重置管理员密码',
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('zh-CN')
}

export default function AdminAudit() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [action, setAction] = useState('')
  const [range, setRange] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const params = new URLSearchParams()
    if (action) params.set('action', action)
    if (range !== 'all') params.set('range', range)
    try {
      const res = await api.get<{ logs: AuditLog[] }>(`/admin/audit?${params.toString()}`)
      setLogs(res.logs)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [action, range])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-900">审计日志</h1>

      <div className="mt-4 flex flex-wrap gap-2">
        <select
          value={range}
          onChange={(e) => setRange(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
        >
          <option value="all">全部时间</option>
          <option value="today">今天</option>
          <option value="7d">近 7 天</option>
          <option value="30d">近 30 天</option>
        </select>
        <input
          type="text"
          value={action}
          onChange={(e) => setAction(e.target.value)}
          placeholder="按操作类型筛选（如 resolve_report_remove）"
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
        />
      </div>

      {error && <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner size={28} />
        </div>
      ) : logs.length === 0 ? (
        <div className="mt-4">
          <EmptyState title="没有审计日志" />
        </div>
      ) : (
        <ul className="mt-4 space-y-2">
          {logs.map((l) => (
            <li key={l.id} className="rounded-lg border border-gray-200 bg-white p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-800">
                  {ACTION_LABELS[l.action] ?? l.action}
                </span>
                <span className="text-xs text-gray-400">{formatTime(l.createdAt)}</span>
              </div>
              <div className="mt-1 text-xs text-gray-500">
                操作人 #{l.actorUserId} · 目标 {l.targetType}#{l.targetId}
                {l.reason && <span> · 理由：{l.reason}</span>}
                {l.detail && <span> · {l.detail}</span>}
              </div>
              <div className="mt-1 text-xs text-gray-400">
                IP {l.actorIp}
                {l.sourcePage && <span> · 来源 {l.sourcePage}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
