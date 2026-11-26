import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import Spinner from '../../components/ui/Spinner'

interface Stats {
  pendingReports: number
  todayReports: number
  activeUsers: number
  deletedUsers: number
  totalPosts: number
  todayPosts: number
  todayComments: number
  deletedMaskPosts: number
}

export default function AdminHome() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const res = await api.get<Stats>('/admin/stats')
      setStats(res)
      setError('')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = setInterval(() => void load(), 30000)
    const onFocus = () => void load()
    window.addEventListener('focus', onFocus)
    return () => {
      clearInterval(timer)
      window.removeEventListener('focus', onFocus)
    }
  }, [load])

  if (!stats) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size={28} />
      </div>
    )
  }

  const cards: { label: string; value: number; to?: string }[] = [
    { label: '待处理举报', value: stats.pendingReports, to: '/admin/reports' },
    { label: '今日新增举报', value: stats.todayReports },
    { label: '正常账号', value: stats.activeUsers },
    { label: '已注销账号', value: stats.deletedUsers },
    { label: '公开帖子', value: stats.totalPosts },
    { label: '今日新增帖子', value: stats.todayPosts },
    { label: '今日新增回应', value: stats.todayComments },
    { label: '已注销面具内容', value: stats.deletedMaskPosts },
  ]

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-900">管理后台</h1>

      {error && <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {cards.map((c) => {
          const inner = (
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="text-xs text-gray-500">{c.label}</div>
              <div className="mt-1 text-2xl font-bold text-gray-900">{c.value}</div>
            </div>
          )
          return c.to ? (
            <Link key={c.label} to={c.to} className="hover:border-gray-300">
              {inner}
            </Link>
          ) : (
            <div key={c.label}>{inner}</div>
          )
        })}
      </div>

      <div className="mt-6 flex gap-3">
        <Link
          to="/admin/reports"
          className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700 hover:bg-gray-50"
        >
          举报队列
        </Link>
        <Link
          to="/admin/admins"
          className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700 hover:bg-gray-50"
        >
          管理员管理
        </Link>
        <Link
          to="/admin/audit"
          className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700 hover:bg-gray-50"
        >
          审计日志
        </Link>
      </div>
    </div>
  )
}
