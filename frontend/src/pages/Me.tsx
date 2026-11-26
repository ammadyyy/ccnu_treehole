import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { Mask } from '../lib/types'
import Button from '../components/ui/Button'
import ConfirmDialog from '../components/ui/ConfirmDialog'

export default function Me() {
  const { user, refresh, logout } = useAuth()
  const [masks, setMasks] = useState<Mask[]>([])
  const [showPicker, setShowPicker] = useState(false)
  const [confirmLogout, setConfirmLogout] = useState(false)
  const [error, setError] = useState('')

  const activeMasks = masks.filter((m) => m.status === 'active')

  useEffect(() => {
    api
      .get<{ masks: Mask[] }>('/masks')
      .then((d) => setMasks(d.masks))
      .catch(() => {
        /* 加载面具列表失败不阻断个人中心展示 */
      })
  }, [])

  const onSwitchMask = async (mask: Mask) => {
    setShowPicker(false)
    setError('')
    try {
      await api.post('/session/current-mask', { maskId: mask.id })
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '切换失败')
    }
  }

  const onLogout = async () => {
    setConfirmLogout(false)
    await logout()
  }

  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin'

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <h1 className="text-xl font-bold text-gray-900">个人中心</h1>

      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <dl className="space-y-3 text-sm">
          <div className="flex items-center justify-between">
            <dt className="text-gray-500">邮箱</dt>
            <dd className="font-medium text-gray-900">{user?.email}</dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-gray-500">当前面具</dt>
            <dd>
              {user?.currentMask ? (
                <button
                  type="button"
                  onClick={() => setShowPicker((v) => !v)}
                  className="font-medium text-gray-900 underline-offset-2 hover:underline"
                >
                  {user.currentMask.token}
                  <span className="ml-1 text-xs text-gray-400">切换</span>
                </button>
              ) : (
                <Link to="/me/masks" className="text-gray-500 hover:text-gray-900">
                  未选择，去领取
                </Link>
              )}
            </dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-gray-500">面具数量</dt>
            <dd className="font-medium text-gray-900">{user?.maskCount ?? 0}</dd>
          </div>
        </dl>

        {showPicker && (
          <div className="mt-3 border-t border-gray-100 pt-3">
            <p className="text-xs text-gray-400">选择要切换到的面具</p>
            <ul className="mt-2 space-y-1">
              {activeMasks.map((m) => (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => onSwitchMask(m)}
                    disabled={user?.currentMask?.id === m.id}
                    className="w-full rounded-md px-2 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-50 disabled:text-gray-400"
                  >
                    {m.token}
                    {user?.currentMask?.id === m.id && (
                      <span className="ml-2 text-xs text-gray-400">当前</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <nav className="space-y-1">
        <Link
          to="/me/masks"
          className="block rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700 hover:bg-gray-50"
        >
          我的面具
        </Link>
        <Link
          to="/me/masks"
          className="block rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700 hover:bg-gray-50"
        >
          我的帖子
        </Link>
        <Link
          to="/me/settings"
          className="block rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700 hover:bg-gray-50"
        >
          账号设置
        </Link>
        {isAdmin && (
          <Link
            to="/admin"
            className="block rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700 hover:bg-gray-50"
          >
            管理后台
          </Link>
        )}
      </nav>

      <Button variant="danger" onClick={() => setConfirmLogout(true)}>
        退出登录
      </Button>

      <ConfirmDialog
        open={confirmLogout}
        title="退出登录"
        message="确定退出登录吗？"
        confirmText="退出登录"
        danger
        onConfirm={onLogout}
        onCancel={() => setConfirmLogout(false)}
      />
    </div>
  )
}
