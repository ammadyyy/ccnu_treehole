import { useState } from 'react'
import { api, ApiError } from '../lib/api'
import Modal from './ui/Modal'
import Button from './ui/Button'

const REPORT_REASONS = ['广告或垃圾信息', '辱骂攻击', '色情低俗', '泄露隐私', '违法违规', '其他']

interface ReportDialogProps {
  open: boolean
  targetType: 'post' | 'comment'
  targetId: number
  onClose: () => void
  onSubmitted: () => void
}

export default function ReportDialog({
  open,
  targetType,
  targetId,
  onClose,
  onSubmitted,
}: ReportDialogProps) {
  const [reason, setReason] = useState('')
  const [detail, setDetail] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const reset = () => {
    setReason('')
    setDetail('')
    setError('')
    setLoading(false)
  }

  const onSubmit = async () => {
    if (!reason) {
      setError('请选择举报原因')
      return
    }
    setLoading(true)
    setError('')
    try {
      await api.post('/reports', { targetType, targetId, reason, detail })
      reset()
      onSubmitted()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '举报失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose}>
      <div className="p-6">
        <h3 className="text-base font-semibold text-gray-900">举报</h3>
        <p className="mt-1 text-xs text-gray-400">
          {targetType === 'post' ? '举报这篇帖子' : '举报这条回应'}
        </p>

        <div className="mt-4">
          <span className="block text-sm font-medium text-gray-700">原因</span>
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

        <div className="mt-4">
          <label htmlFor="report-detail" className="block text-sm font-medium text-gray-700">
            补充说明（可选）
          </label>
          <textarea
            id="report-detail"
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            rows={3}
            maxLength={200}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
          />
          <div className="mt-1 text-right text-xs text-gray-400">{detail.length}/200</div>
        </div>

        {error && <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button onClick={onSubmit} loading={loading} disabled={loading}>
            提交举报
          </Button>
        </div>
      </div>
    </Modal>
  )
}
