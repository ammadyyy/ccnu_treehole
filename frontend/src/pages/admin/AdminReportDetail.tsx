import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import Button from '../../components/ui/Button'
import EmptyState from '../../components/ui/EmptyState'
import Modal from '../../components/ui/Modal'
import Spinner from '../../components/ui/Spinner'

const REPORT_REASONS = ['广告或垃圾信息', '辱骂攻击', '色情低俗', '泄露隐私', '违法违规', '其他']

interface ReportRecord {
  id: number
  reason: string
  detail: string | null
  status: string
  reporterUserId: number
  reporterEmail: string
  reporterMaskId: number | null
  reporterIp: string
  handledReason: string | null
  handledDetail: string | null
  handledAt: string | null
  createdAt: string
}

interface ReportNote {
  id: number
  adminId: number
  body: string
  createdAt: string
}

interface ReportContext {
  type: 'post' | 'comment'
  id: number
  title?: string
  body?: string
  tags?: string[]
  maskToken?: string
  postId?: number
  createdAt: string
}

interface ReportDetail {
  targetType: 'post' | 'comment'
  targetId: number
  reports: ReportRecord[]
  notes: ReportNote[]
  context: ReportContext | null
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('zh-CN')
}

export default function AdminReportDetail() {
  const { id } = useParams<{ id: string }>()
  const [detail, setDetail] = useState<ReportDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [resolveOpen, setResolveOpen] = useState(false)
  const [action, setAction] = useState<'keep' | 'remove'>('keep')
  const [reason, setReason] = useState('')
  const [resolveDetail, setResolveDetail] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [opError, setOpError] = useState('')

  const [noteBody, setNoteBody] = useState('')
  const [noteBusy, setNoteBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get<ReportDetail>(`/admin/reports/${id}`)
      setDetail(res)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  const openResolve = (act: 'keep' | 'remove') => {
    setAction(act)
    setReason('')
    setResolveDetail('')
    setOpError('')
    setResolveOpen(true)
  }

  const confirmResolve = () => {
    if (!reason) {
      setOpError('请选择处理理由')
      return
    }
    if (resolveDetail.trim().length < 10) {
      setOpError('请填写至少 10 字的处理说明')
      return
    }
    setConfirmOpen(true)
  }

  const doResolve = async () => {
    setBusy(true)
    setOpError('')
    try {
      await api.post(`/admin/reports/${id}/resolve`, {
        action,
        reason,
        detail: resolveDetail.trim(),
      })
      setConfirmOpen(false)
      setResolveOpen(false)
      await load()
    } catch (e) {
      setOpError(e instanceof ApiError ? e.message : '处理失败')
    } finally {
      setBusy(false)
    }
  }

  const addNote = async () => {
    if (!noteBody.trim()) return
    setNoteBusy(true)
    setError('')
    try {
      await api.post(`/admin/reports/${id}/notes`, { body: noteBody.trim() })
      setNoteBody('')
      await load()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '备注失败')
    } finally {
      setNoteBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size={28} />
      </div>
    )
  }

  if (!detail) {
    return <EmptyState title="举报不存在" />
  }

  const allResolved = detail.reports.every((r) => r.status !== 'open')

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">举报详情</h1>
        <span className="text-xs text-gray-400">
          {detail.targetType === 'post' ? '帖子' : '回应'} #{detail.targetId}
        </span>
      </div>

      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {/* 目标内容上下文 */}
      {detail.context && (
        <section className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="text-sm font-medium text-gray-500">被举报内容</h2>
          {detail.context.title && (
            <p className="mt-2 font-medium text-gray-900">{detail.context.title}</p>
          )}
          <p className="preserve-text mt-1 text-sm text-gray-700">
            {detail.context.body}
          </p>
          <div className="mt-2 text-xs text-gray-400">
            {detail.context.maskToken && <span>{detail.context.maskToken} · </span>}
            <span>{formatTime(detail.context.createdAt)}</span>
          </div>
        </section>
      )}

      {/* 举报记录（旧→新） */}
      <section>
        <h2 className="text-sm font-medium text-gray-500">举报记录（{detail.reports.length}）</h2>
        <ul className="mt-2 space-y-2">
          {detail.reports.map((r) => (
            <li key={r.id} className="rounded-lg border border-gray-100 bg-white p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-800">{r.reason}</span>
                <span className="text-xs text-gray-400">{formatTime(r.createdAt)}</span>
              </div>
              {r.detail && <p className="mt-1 text-gray-600">{r.detail}</p>}
              <div className="mt-1 text-xs text-gray-400">
                举报者 {r.reporterEmail} · IP {r.reporterIp}
              </div>
            </li>
          ))}
        </ul>
      </section>

      {/* 内部备注（新→旧） */}
      <section>
        <h2 className="text-sm font-medium text-gray-500">内部备注</h2>
        {detail.notes.length === 0 ? (
          <p className="mt-2 text-xs text-gray-400">暂无备注</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {detail.notes.map((n) => (
              <li key={n.id} className="rounded-lg border border-gray-100 bg-gray-50 p-3 text-sm">
                <p className="text-gray-700">{n.body}</p>
                <div className="mt-1 text-xs text-gray-400">
                  管理员 #{n.adminId} · {formatTime(n.createdAt)}
                </div>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 flex gap-2">
          <input
            type="text"
            value={noteBody}
            onChange={(e) => setNoteBody(e.target.value)}
            placeholder="追加内部备注…"
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
          <Button onClick={addNote} loading={noteBusy} disabled={noteBusy || !noteBody.trim()}>
            添加
          </Button>
        </div>
      </section>

      {/* 处理 */}
      {!allResolved && (
        <div className="flex gap-3">
          <Button variant="secondary" onClick={() => openResolve('keep')}>
            保留内容
          </Button>
          <Button variant="danger" onClick={() => openResolve('remove')}>
            删除内容
          </Button>
        </div>
      )}

      {/* 处理弹窗 */}
      <Modal open={resolveOpen} onClose={() => setResolveOpen(false)}>
        <div className="p-6">
          <h3 className="text-base font-semibold text-gray-900">
            {action === 'keep' ? '保留内容' : '删除内容'}
          </h3>
          <div className="mt-4">
            <span className="block text-sm font-medium text-gray-700">处理理由</span>
            <div className="mt-2 flex flex-wrap gap-2">
              {REPORT_REASONS.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setReason(r)}
                  className={`rounded-full px-3 py-1 text-sm ${
                    reason === r ? 'bg-gray-900 text-white' : 'bg-white text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
          <textarea
            value={resolveDetail}
            onChange={(e) => setResolveDetail(e.target.value)}
            rows={3}
            placeholder="处理说明（至少 10 字）"
            className="mt-4 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
          {opError && <p className="mt-3 text-sm text-red-600">{opError}</p>}
          <div className="mt-5 flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setResolveOpen(false)}>
              取消
            </Button>
            <Button variant={action === 'remove' ? 'danger' : 'primary'} onClick={confirmResolve}>
              提交
            </Button>
          </div>
        </div>
      </Modal>

      {/* 二次确认 */}
      <Modal open={confirmOpen} onClose={() => setConfirmOpen(false)}>
        <div className="p-6">
          <h3 className="text-base font-semibold text-gray-900">确认{action === 'remove' ? '删除' : '保留'}</h3>
          <p className="mt-2 text-sm text-gray-600">
            {action === 'remove'
              ? '删除后不可恢复，该目标的全部举报将统一结案。确定删除吗？'
              : '保留后内容继续公开，该目标的全部举报将统一结案。确定保留吗？'}
          </p>
          <div className="mt-5 flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
              取消
            </Button>
            <Button
              variant={action === 'remove' ? 'danger' : 'primary'}
              onClick={doResolve}
              loading={busy}
              disabled={busy}
            >
              确认
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
