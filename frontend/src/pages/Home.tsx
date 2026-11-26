import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import { TAGS, imageUrl, type PostCard } from '../lib/types'
import EmptyState from '../components/ui/EmptyState'
import Spinner from '../components/ui/Spinner'

type Sort = 'latest' | 'hot'

function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const diff = Date.now() - d.getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day} 天前`
  return d.toLocaleDateString('zh-CN')
}

function maskLabel(token: string, status: string): string {
  if (status === 'destroyed') return `${token} · 已销毁面具`
  if (status === 'deleted') return '已注销面具'
  return token
}

export default function Home() {
  const [sort, setSort] = useState<Sort>('latest')
  const [tag, setTag] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [posts, setPosts] = useState<PostCard[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const sentinelRef = useRef<HTMLDivElement>(null)

  const loadLatest = useCallback(
    async (reset: boolean) => {
      const params = new URLSearchParams({ sort: 'latest' })
      if (tag) params.set('tag', tag)
      if (!reset && cursor) params.set('cursor', cursor)
      const res = await api.get<{ posts: PostCard[]; nextCursor: string | null }>(
        `/posts?${params.toString()}`,
      )
      setPosts((prev) => (reset ? res.posts : [...prev, ...res.posts]))
      setCursor(res.nextCursor)
    },
    [tag, cursor],
  )

  const loadHot = useCallback(async () => {
    const params = new URLSearchParams()
    if (tag) params.set('tag', tag)
    const res = await api.get<{ posts: PostCard[]; nextCursor: string | null }>(
      `/posts/hot?${params.toString()}`,
    )
    setPosts(res.posts)
    setCursor(null)
  }, [tag])

  const loadSearch = useCallback(
    async (reset: boolean) => {
      const params = new URLSearchParams({ q: query })
      if (tag) params.set('tag', tag)
      if (!reset && cursor) params.set('cursor', cursor)
      const res = await api.get<{ posts: PostCard[]; nextCursor: string | null }>(
        `/search?${params.toString()}`,
      )
      setPosts((prev) => (reset ? res.posts : [...prev, ...res.posts]))
      setCursor(res.nextCursor)
    },
    [query, tag, cursor],
  )

  // 排序/标签/搜索词变化时重置加载
  useEffect(() => {
    setLoading(true)
    setError('')
    const fn = query ? loadSearch(true) : sort === 'latest' ? loadLatest(true) : loadHot()
    fn
      .catch((e: Error) => setError(e instanceof ApiError ? e.message : '加载失败'))
      .finally(() => setLoading(false))
  }, [query, sort, tag, loadLatest, loadHot, loadSearch])

  // 列表滚动加载（最新或搜索）
  useEffect(() => {
    if ((!query && sort !== 'latest') || !cursor || loadingMore) return
    const el = sentinelRef.current
    if (!el) return
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setLoadingMore(true)
          const fn = query ? loadSearch(false) : loadLatest(false)
          fn
            .catch(() => {})
            .finally(() => setLoadingMore(false))
        }
      },
      { rootMargin: '200px' },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [query, sort, cursor, loadingMore, loadLatest, loadSearch])

  const selectTag = (t: string | null) => {
    setTag(t)
    setPosts([])
    setCursor(null)
  }

  return (
    <div>
      {/* 搜索框 */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          setQuery(searchInput.trim())
          setPosts([])
          setCursor(null)
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="搜索标题、正文、回应…"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
        />
        <button
          type="submit"
          className="shrink-0 rounded-md bg-gray-900 px-4 py-2 text-sm text-white hover:bg-gray-700"
        >
          搜索
        </button>
      </form>

      {query && (
        <p className="mt-2 text-xs text-gray-400">
          搜索「{query}」
          <button
            type="button"
            onClick={() => {
              setQuery('')
              setSearchInput('')
              setPosts([])
              setCursor(null)
            }}
            className="ml-2 text-gray-500 underline"
          >
            清除
          </button>
        </p>
      )}

      {/* 排序切换（仅非搜索状态） */}
      {!query && (
      <div className="mt-3 flex gap-2">
        {(['latest', 'hot'] as Sort[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSort(s)}
            className={`rounded-full px-4 py-1.5 text-sm ${
              sort === s ? 'bg-gray-900 text-white' : 'bg-white text-gray-600 hover:bg-gray-100'
            }`}
          >
            {s === 'latest' ? '最新' : '24 小时最热'}
          </button>
        ))}
      </div>
      )}

      {/* 标签筛选 */}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => selectTag(null)}
          className={`rounded-full px-3 py-1 text-sm ${
            tag === null ? 'bg-gray-200 text-gray-900' : 'bg-white text-gray-500 hover:bg-gray-100'
          }`}
        >
          全部
        </button>
        {TAGS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => selectTag(t)}
            className={`rounded-full px-3 py-1 text-sm ${
              tag === t ? 'bg-gray-200 text-gray-900' : 'bg-white text-gray-500 hover:bg-gray-100'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {error && <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {/* 列表 */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner size={28} />
        </div>
      ) : posts.length === 0 ? (
        <div className="mt-4">
          <EmptyState title="没有相关内容" description="换个标签或稍后再来看看" />
        </div>
      ) : (
        <ul className="mt-4 space-y-3">
          {posts.map((p) => (
            <li key={p.id}>
              <Link
                to={`/post/${p.id}`}
                className="block rounded-lg border border-gray-200 bg-white p-4 hover:border-gray-300"
              >
                <div className="text-base font-semibold text-gray-900">{p.title}</div>
                {p.thumbnail && (
                  <div className="relative mt-3 overflow-hidden rounded-md">
                    <img
                      src={imageUrl(p.thumbnail)}
                      alt={p.title}
                      loading="lazy"
                      className="max-h-60 w-full object-contain"
                    />
                    {p.imageCount > 1 && (
                      <span className="absolute bottom-2 right-2 rounded bg-black/60 px-1.5 py-0.5 text-xs text-white">
                        {p.imageCount} 张
                      </span>
                    )}
                  </div>
                )}
                <p className="preserve-text mt-2 text-sm text-gray-600">{p.excerpt}</p>
                <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-400">
                  <span>{maskLabel(p.mask.token, p.mask.status)}</span>
                  {p.tags.map((t) => (
                    <span key={t} className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-500">
                      {t}
                    </span>
                  ))}
                  <span>{p.commentCount} 回应</span>
                  <span>{formatTime(p.createdAt)}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {/* 滚动加载哨兵（最新列表或搜索） */}
      {(query || sort === 'latest') && (
        <div ref={sentinelRef} className="flex justify-center py-4">
          {loadingMore ? <Spinner /> : cursor ? null : <span className="text-xs text-gray-400">已经到底了</span>}
        </div>
      )}
    </div>
  )
}
