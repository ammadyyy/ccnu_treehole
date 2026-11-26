import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../lib/api'
import Button from '../../components/ui/Button'
import EmptyState from '../../components/ui/EmptyState'
import Modal from '../../components/ui/Modal'
import Spinner from '../../components/ui/Spinner'

interface AdminItem {
  id: number
  email: string
  role: 'admin' | 'super_admin'
  status: 'active' | 'disabled'
  createdAt: string
}

type OpType = 'create' | 'disable' | 'restore' | 'reset'

export default function AdminAdmins() {
  const [admins, setAdmins] = useState<AdminItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const [op, setOp] = useState<OpType | null>(null)
  const [target, setTarget] = useState<AdminItem | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [reason, setReason] = useState('')
  const [opError, setOpError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get<{ admins: AdminItem[] }>('/admin/admins')
      setAdmins(res.admins)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const openOp = (type: OpType, t?: AdminItem) => {
    setOp(type)
    setTarget(t ?? null)
    setEmail('')
    setPassword('')
    setReason('')
    setOpError('')
  }

  const closeOp = () => {
    setOp(null)
    setTarget(null)
    setOpError('')
  }

  const submitOp = async () => {
    if (op === 'create') {
      if (!email || !password) {
        setOpError('请填写邮箱和密码')
        return
      }
    } else if (reason.trim().length < 10) {
      setOpError('请填写至少 10 字的操作理由')
      return
    }
    setBusy(true)
    setOpError('')
    try {
      if (op === 'create') {
        await api.post('/admin/admins', { email, password, reason })
      } else if (op === 'disable' && target) {
        await api.post(`/admin/admins/${target.id}/disable`, { reason })
      } else if (op === 'restore' && target) {
        await api.post(`/admin/admins/${target.id}/restore`, { reason })
      } else if (op === 'reset' && target) {
        if (!password) {
          setOpError('请填写新密码')
          return
        }
        await api.post(`/admin/admins/${target.id}/reset-password`, { password, reason })
      }
      closeOp()
      await load()
    } catch (e) {
      setOpError(e instanceof ApiError ? e.message : '操作失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">管理员管理</h1>
        <Button onClick={() => openOp('create')}>创建管理员</Button>
      </div>

      {error && <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner size={28} />
        </div>
      ) : admins.length === 0 ? (
        <div className="mt-4">
          <EmptyState title="没有管理员" />
        </div>
      ) : (
        <ul className="mt-4 space-y-2">
          {admins.map((a) => (
            <li key={a.id} className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4">
              <div>
                <div className="text-sm font-medium text-gray-900">{a.email}</div>
                <div className="mt-1 text-xs text-gray-400">
                  {a.role === 'super_admin' ? '超级管理员' : '普通管理员'} ·{' '}
                  {a.status === 'active' ? '正常' : '已停用'}
                </div>
              </div>
              {a.role !== 'super_admin' && (
                <div className="flex gap-2">
                  {a.status === 'active' ? (
                    <Button variant="secondary" onClick={() => openOp('disable', a)}>
                      停用
                    </Button>
                  ) : (
                    <Button variant="secondary" onClick={() => openOp('restore', a)}>
                      恢复
                    </Button>
                  )}
                  <Button variant="secondary" onClick={() => openOp('reset', a)}>
                    重置密码
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <Modal open={op !== null} onClose={closeOp}>
        <div className="p-6">
          <h3 className="text-base font-semibold text-gray-900">
            {op === 'create'
              ? '创建管理员'
              : op === 'disable'
                ? '停用管理员'
                : op === 'restore'
                  ? '恢复管理员'
                  : '重置密码'}
          </h3>
          {target && <p className="mt-1 text-sm text-gray-500">{target.email}</p>}

          <div className="mt-4 space-y-3">
            {op === 'create' && (
              <>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="邮箱（未注册）"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="临时密码（至少 8 位含字母数字）"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </>
            )}
            {op === 'reset' && (
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="新密码（至少 8 位含字母数字）"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            )}
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="操作理由（至少 10 字）"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          {opError && <p className="mt-3 text-sm text-red-600">{opError}</p>}

          <div className="mt-5 flex justify-end gap-3">
            <Button variant="secondary" onClick={closeOp}>
              取消
            </Button>
            <Button onClick={submitOp} loading={busy} disabled={busy}>
              确认
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
