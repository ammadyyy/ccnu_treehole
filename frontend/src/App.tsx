import { Outlet, ScrollRestoration } from 'react-router-dom'
import Navbar from './components/Navbar'

/**
 * 应用布局：顶部导航 + 路由出口 + 滚动位置恢复。
 * 使用 data router（createBrowserRouter）时，ScrollRestoration 自动保存/恢复
 * 树洞墙、通知、搜索等列表页的滚动位置。
 */
export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <ScrollRestoration />
      <Navbar />
      <main className="mx-auto max-w-2xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
