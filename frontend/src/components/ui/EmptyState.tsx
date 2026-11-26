interface EmptyStateProps {
  title?: string
  description?: string
}

/** 空状态占位，用于列表、搜索、通知等无数据场景。 */
export default function EmptyState({ title = '这里空空如也', description }: EmptyStateProps) {
  return (
    <div className="rounded-lg bg-white py-12 text-center">
      <div className="text-sm font-medium text-gray-600">{title}</div>
      {description && <div className="mt-1 text-xs text-gray-400">{description}</div>}
    </div>
  )
}
