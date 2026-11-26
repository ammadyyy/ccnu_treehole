interface SpinnerProps {
  size?: number
}

/** 加载指示器。 */
export default function Spinner({ size = 20 }: SpinnerProps) {
  return (
    <span
      className="inline-block animate-spin rounded-full border-2 border-gray-300 border-t-gray-700"
      style={{ width: size, height: size }}
      role="status"
      aria-label="加载中"
    />
  )
}
