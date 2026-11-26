import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function Home() {
  const [health, setHealth] = useState<string>('检测中…')

  useEffect(() => {
    api
      .get<{ status: string; service: string }>('/health')
      .then((d) => setHealth(`${d.status} · ${d.service}`))
      .catch((e: Error) => setHealth(`后端未连接：${e.message}`))
  }, [])

  return (
    <div>
      <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center">
        <div className="text-lg font-medium text-gray-700">树洞墙</div>
        <div className="mt-3 text-sm text-gray-400">帖子列表将在 T-13 实现。</div>
      </div>
      <div className="mt-3 text-xs text-gray-400">健康检查：{health}</div>
    </div>
  )
}
