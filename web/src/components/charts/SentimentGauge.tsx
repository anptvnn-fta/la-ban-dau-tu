/**
 * Đồng hồ tâm lý thị trường (0-100), nửa cung tròn SVG.
 * Màu chuyển đỏ (bi quan) → vàng (trung tính) → xanh (lạc quan).
 * Có nhãn số + chữ để không chỉ dựa vào màu.
 */
export function SentimentGauge({
  score,
  label,
  size = 160,
}: {
  score: number
  label?: string
  size?: number
}) {
  const clamped = Math.max(0, Math.min(100, score))
  const radius = size / 2 - 12
  const cx = size / 2
  const cy = size / 2
  const circumference = Math.PI * radius // nửa cung
  const dash = (clamped / 100) * circumference

  const color =
    clamped >= 60 ? 'var(--price-up)' : clamped >= 40 ? 'var(--warning)' : 'var(--price-down)'

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 16} viewBox={`0 0 ${size} ${size / 2 + 16}`} role="img" aria-label={`Tâm lý ${clamped}/100`}>
        {/* nền cung */}
        <path
          d={`M 12 ${cy} A ${radius} ${radius} 0 0 1 ${size - 12} ${cy}`}
          fill="none"
          stroke="var(--border)"
          strokeWidth={10}
          strokeLinecap="round"
        />
        {/* cung giá trị */}
        <path
          d={`M 12 ${cy} A ${radius} ${radius} 0 0 1 ${size - 12} ${cy}`}
          fill="none"
          stroke={color}
          strokeWidth={10}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
          style={{ transition: 'stroke-dasharray 600ms ease' }}
        />
        <text x={cx} y={cy - 6} textAnchor="middle" className="fill-foreground font-mono" style={{ fontSize: size * 0.22, fontWeight: 700 }}>
          {clamped}
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" className="fill-muted-foreground" style={{ fontSize: 11 }}>
          / 100
        </text>
      </svg>
      {label ? <p className="-mt-1 text-sm font-medium text-foreground">{label}</p> : null}
    </div>
  )
}
