import { useEffect, type ReactNode } from 'react'

interface ModalProps {
  open: boolean
  onClose: () => void
  closeOnOverlay?: boolean
  children: ReactNode
}

/**
 * 通用模态框：支持 Esc 关闭、背景滚动锁定、可选遮罩点击关闭。
 * 图片大图预览需要「不点遮罩关闭」时，将 closeOnOverlay 设为 false。
 */
export default function Modal({ open, onClose, closeOnOverlay = true, children }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={closeOnOverlay ? onClose : undefined}
      />
      <div className="relative z-10 w-full max-w-md rounded-lg bg-white shadow-xl">
        {children}
      </div>
    </div>
  )
}
