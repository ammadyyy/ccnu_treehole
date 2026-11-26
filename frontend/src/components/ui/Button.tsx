import type { ReactNode } from 'react'

interface ButtonProps {
  type?: 'button' | 'submit'
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  loading?: boolean
  disabled?: boolean
  onClick?: () => void
  children: ReactNode
}

const styles: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary: 'bg-gray-900 text-white hover:bg-gray-700 disabled:bg-gray-400',
  secondary: 'border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:text-gray-400',
  danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-400',
  ghost: 'text-gray-600 hover:text-gray-900',
}

/** 通用按钮。 */
export default function Button({
  type = 'button',
  variant = 'primary',
  loading = false,
  disabled = false,
  onClick,
  children,
}: ButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`rounded-md px-4 py-2 text-sm transition-colors disabled:cursor-not-allowed ${styles[variant]}`}
    >
      {loading ? '处理中…' : children}
    </button>
  )
}
