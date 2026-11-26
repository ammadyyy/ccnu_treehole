import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

/**
 * 顶部导航栏。
 * 游客态：回声洞 / 首页 / 登录 / 注册
 * 登录态：回声洞 / 首页 / 写树洞 / 通知 / 个人中心
 * 登录态通知入口显示未读红点与数量（>99 显示 99+，0 隐藏），30 秒轮询 + 页面聚焦刷新。
 */
export default function Navbar() {
  const { user, loading } = useAuth()
  const [unread, setUnread] = useState(0)
  const loggedIn = !!user

  const fetchUnread = useCallback(async () => {
    try {
      const res = await api.get<{ unreadCount: number }>('/notifications')
      setUnread(res.unreadCount)
    } catch {
      setUnread(0)
    }
  }, [])

  useEffect(() => {
    if (!loggedIn) {
      setUnread(0)
      return
    }
    void fetchUnread()
    const timer = setInterval(() => void fetchUnread(), 30000)
    const onFocus = () => void fetchUnread()
    const onUpdate = () => void fetchUnread()
    window.addEventListener('focus', onFocus)
    window.addEventListener('notifications-updated', onUpdate)
    return () => {
      clearInterval(timer)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('notifications-updated', onUpdate)
    }
  }, [loggedIn, fetchUnread])

  const unreadLabel = unread > 99 ? '99+' : String(unread)

  return (
    <header className="sticky top-0 z-20 border-b border-gray-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-2xl items-center gap-4 px-4 py-3">
        <Link to="/" className="text-lg font-bold tracking-wide text-gray-900">
          回声洞
        </Link>
        <nav className="flex flex-1 items-center gap-4 text-sm text-gray-600">
          <NavLink
            to="/"
            className={({ isActive }) => (isActive ? 'font-medium text-gray-900' : 'hover:text-gray-900')}
          >
            首页
          </NavLink>
          {loggedIn && (
            <>
              <NavLink
                to="/new"
                className={({ isActive }) =>
                  isActive ? 'font-medium text-gray-900' : 'hover:text-gray-900'
                }
              >
                写树洞
              </NavLink>
              <NavLink
                to="/me/notifications"
                className={({ isActive }) =>
                  isActive ? 'font-medium text-gray-900' : 'hover:text-gray-900'
                }
              >
                <span className="inline-flex items-center">
                  通知
                  {unread > 0 && (
                    <span className="ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-xs text-white">
                      {unreadLabel}
                    </span>
                  )}
                </span>
              </NavLink>
            </>
          )}
        </nav>
        <div className="flex items-center gap-3 text-sm">
          {loading ? null : loggedIn ? (
            <Link to="/me" className="text-gray-600 hover:text-gray-900">
              个人中心
            </Link>
          ) : (
            <>
              <Link to="/login" className="text-gray-600 hover:text-gray-900">
                登录
              </Link>
              <Link
                to="/register"
                className="rounded-md bg-gray-900 px-3 py-1.5 text-gray-50 hover:bg-gray-700"
              >
                注册
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
