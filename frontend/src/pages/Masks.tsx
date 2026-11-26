import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { Mask } from '../lib/types'
import Button from '../components/ui/Button'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import EmptyState from '../components/ui/EmptyState'
import Spinner from '../components/ui/Spinner'

export default function Masks() {
  const { user, refresh } = useAuth()
  const [masks, setMasks] = useState<Mask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmCreate, setConfirmCreate] = useState(false)
  const [confirmDestroy, setConfirmDestroy] = useState<Mask | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.get<{ masks: Mask[] }>('/masks')
      setMasks(data.masks)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '加载面具失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const onCreate = async () => {
    setConfirmCreate(false)
    setBusy(true)
    try {
      await api.post('/masks')
      await load()
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '领取失败')
    } finally {
      setBusy(false)
    }
  }

  const onDestroy = async () => {
    if (!confirmDestroy) return
    setBusy(true)
    try {
      await api.del(`/masks/${confirmDestroy.id}`)
      setConfirmDestroy(null)
      await load()
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '销毁失败')
    } finally {
      setBusy(false)
    }
  }

  const onSetCurrent = async (mask: Mask) => {
    setBusy(true)
    setError('')
    try {
      await api.post('/session/current-mask', { maskId: mask.id })
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '切换失败')
    } finally {
      setBusy(false)
    }
  }

  const active = masks.filter((m) => m.status === 'active')
  const destroyed = masks.filter((m) => m.status === 'destroyed')

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size={28} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">我的面具</h1>
        <Button onClick={() => setConfirmCreate(true)} disabled={busy || active.length >= 5}>
          领取面具
        </Button>
      </div>

      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {masks.length === 0 ? (
        <EmptyState title="还没有面具" description="领取一个面具后才能发帖和回应" />
      ) : (
        <>
          <section>
            <h2 className="text-sm font-medium text-gray-500">可用面具（{active.length}/5）</h2>
            {active.length === 0 ? (
              <EmptyState title="没有可用面具" description="点击右上角领取新面具" />
            ) : (
              <ul className="mt-3 space-y-3">
                {active.map((m) => (
                  <li key={m.id} className="rounded-lg border border-gray-200 bg-white p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-medium text-gray-900">{m.token}</span>
                        {user?.currentMask?.id === m.id && (
                          <span className="ml-2 rounded bg-gray-900 px-1.5 py-0.5 text-xs text-white">
                            当前
                          </span>
                        )}
                        <div className="mt-1 text-xs text-gray-500">
                          {m.postCount} 帖 · {m.commentCount} 回应
                        </div>
                      </div>
                      <div className="flex gap-2">
                        {user?.currentMask?.id !== m.id && (
                          <Button variant="secondary" onClick={() => onSetCurrent(m)} disabled={busy}>
                            设为当前
                          </Button>
                        )}
                        <Button variant="danger" onClick={() => setConfirmDestroy(m)} disabled={busy}>
                          销毁
                        </Button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {destroyed.length > 0 && (
            <section>
              <h2 className="text-sm font-medium text-gray-500">已销毁面具</h2>
              <ul className="mt-3 space-y-2">
                {destroyed.map((m) => (
                  <li
                    key={m.id}
                    className="rounded-lg border border-dashed border-gray-200 bg-gray-50 p-3 text-sm text-gray-400"
                  >
                    <span className="line-through">{m.token}</span>
                    <span className="ml-2">已销毁面具</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      <ConfirmDialog
        open={confirmCreate}
        title="领取新面具"
        message={`将生成一个新的随机面具。每个账号最多同时持有 5 个可用面具，面具名称一旦销毁，永久不再复用。当前已有 ${active.length} 个。`}
        confirmText="领取"
        onConfirm={onCreate}
        onCancel={() => setConfirmCreate(false)}
      />
      <ConfirmDialog
        open={confirmDestroy !== null}
        title="销毁面具"
        message={
          confirmDestroy
            ? `确定销毁 ${confirmDestroy.token} 吗？销毁后无法继续使用，历史帖子和回应仍会保留，但会标记为「已销毁面具」。该面具发布过 ${confirmDestroy.postCount} 个帖子、回应过 ${confirmDestroy.commentCount} 次。`
            : ''
        }
        confirmText="销毁"
        danger
        onConfirm={onDestroy}
        onCancel={() => setConfirmDestroy(null)}
      />
    </div>
  )
}
