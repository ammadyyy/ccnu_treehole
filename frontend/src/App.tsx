import { Routes, Route, Link } from 'react-router-dom'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white px-4 py-3">
        <Link to="/" className="text-lg font-bold text-gray-900">
          回声洞
        </Link>
      </header>
      <main className="mx-auto max-w-2xl px-4 py-6">
        <Routes>
          <Route path="/" element={<div className="text-gray-600">树洞墙（开发中）</div>} />
        </Routes>
      </main>
    </div>
  )
}
