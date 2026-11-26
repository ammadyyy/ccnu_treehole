import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import Button from '../components/ui/Button'

const PASSWORD_RE = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/

export default function Settings() {
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [passwordLoading, setPasswordLoading] = useState(false)
  const [passwordSuccess, setPasswordSuccess] = useState('')

  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deletePassword, setDeletePassword] = useState('')
  const [deleteError, setDeleteError] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)

  const onChangePassword = async (e: FormEvent) => {
    e.preventDefault()
    setPasswordError('')
    setPasswordSuccess('')
    if (!PASSWORD_RE.test(newPassword)) {
      setPasswordError('新密码至少 8 位，需同时包含字母和数字')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('两次输入的新密码不一致')
      return
    }
    setPasswordLoading(true)
    try {
      const res = await api.post<{ message: string }>('/me/password', {
        currentPassword,
        newPassword,
        confirmPassword,
      })
      setPasswordSuccess(res.message ?? '密码修改成功')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : '修改失败')
    } finally {
      setPasswordLoading(false)
    }
  }

  const onDeleteAccount = async () => {
    setDeleteError('')
    setDeleteLoading(true)
    try {
      await api.post('/me/delete', { password: deletePassword })
      setConfirmDelete(false)
      await refresh()
      navigate('/')
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : '注销失败')
    } finally {
      setDeleteLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-8">
      <h1 className="text-xl font-bold text-gray-900">账号设置</h1>

      {/* 修改密码 */}
      <section className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="text-base font-semibold text-gray-900">修改密码</h2>
        <form onSubmit={onChangePassword} className="mt-4 space-y-4">
          <div>
            <label htmlFor="current" className="block text-sm font-medium text-gray-700">
              当前密码
            </label>
            <input
              id="current"
              type="password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="new" className="block text-sm font-medium text-gray-700">
              新密码
            </label>
            <input
              id="new"
              type="password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
            />
            <p className="mt-1 text-xs text-gray-400">至少 8 位，需同时包含字母和数字</p>
          </div>
          <div>
            <label htmlFor="confirm" className="block text-sm font-medium text-gray-700">
              确认新密码
            </label>
            <input
              id="confirm"
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
            />
          </div>
          {passwordError && <p className="text-sm text-red-600">{passwordError}</p>}
          {passwordSuccess && <p className="text-sm text-green-600">{passwordSuccess}</p>}
          <Button type="submit" loading={passwordLoading} disabled={passwordLoading}>
            修改密码
          </Button>
        </form>
      </section>

      {/* 注销账号 */}
      <section className="rounded-lg border border-red-200 bg-white p-5">
        <h2 className="text-base font-semibold text-red-600">注销账号</h2>
        <p className="mt-1 text-sm text-gray-500">
          注销后无法登录，历史帖子和回应保留但会显示「已注销面具」，通知会被删除，原邮箱可以重新注册。
        </p>
        <div className="mt-4">
          <Button variant="danger" onClick={() => setConfirmDelete(true)}>
            注销账号
          </Button>
        </div>
      </section>

      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50" onClick={() => setConfirmDelete(false)} />
          <div className="relative z-10 w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
            <h3 className="text-base font-semibold text-gray-900">注销账号</h3>
            <p className="mt-2 text-sm text-gray-600">
              注销后不可登录，历史内容保留。请输入密码确认注销。
            </p>
            <input
              type="password"
              value={deletePassword}
              onChange={(e) => setDeletePassword(e.target.value)}
              placeholder="输入当前密码"
              className="mt-4 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
            />
            {deleteError && <p className="mt-2 text-sm text-red-600">{deleteError}</p>}
            <div className="mt-5 flex justify-end gap-3">
              <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
                取消
              </Button>
              <Button variant="danger" onClick={onDeleteAccount} loading={deleteLoading} disabled={deleteLoading}>
                确认注销
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
