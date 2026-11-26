interface Props {
  title?: string
  children?: React.ReactNode
}

/** 通用页面占位，后续任务逐个替换为真实实现。 */
export default function Placeholder({ title, children }: Props) {
  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center">
      <div className="text-lg font-medium text-gray-700">{title ?? '开发中'}</div>
      {children ? (
        <div className="mt-3 text-sm text-gray-500">{children}</div>
      ) : (
        <div className="mt-3 text-sm text-gray-400">该页面将在对应任务中实现。</div>
      )}
    </div>
  )
}
