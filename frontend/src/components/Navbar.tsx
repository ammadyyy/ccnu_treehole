import { Link, NavLink } from 'react-router-dom'

/**
 * 顶部导航栏。
 * 游客态：回声洞 / 搜索 / 登录 / 注册
 * 登录态：回声洞 / 搜索 / 写树洞 / 通知 / 个人中心
 * 当前先做静态游客态结构；登录态与未读通知在后续任务接入。
 */
export default function Navbar() {
  return (
    <header className="sticky top-0 z-20 border-b border-gray-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-2xl items-center gap-4 px-4 py-3">
        <Link to="/" className="text-lg font-bold tracking-wide text-gray-900">
          回声洞
        </Link>
        <nav className="flex flex-1 items-center gap-4 text-sm text-gray-600">
          <NavLink
            to="/"
            className={({ isActive }) => (isActive ? 'text-gray-900 font-medium' : 'hover:text-gray-900')}
          >
            首页
          </NavLink>
          <span className="text-gray-300">搜索</span>
        </nav>
        <div className="flex items-center gap-3 text-sm">
          <Link to="/login" className="text-gray-600 hover:text-gray-900">
            登录
          </Link>
          <Link
            to="/register"
            className="rounded-md bg-gray-900 px-3 py-1.5 text-gray-50 hover:bg-gray-700"
          >
            注册
          </Link>
        </div>
      </div>
    </header>
  )
}
