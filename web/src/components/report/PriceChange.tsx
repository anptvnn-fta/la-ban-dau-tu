import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { fmtPrice, fmtPct } from '@/utils/num'

/**
 * Hiển thị giá + % thay đổi theo quy ước VN (xanh tăng / đỏ giảm),
 * kèm icon ▲▼ để không chỉ phụ thuộc màu sắc (a11y).
 */
export function PriceChange({
  price,
  changePct,
  size = 'md',
}: {
  price?: number | null
  changePct?: number | null
  size?: 'sm' | 'md' | 'lg'
}) {
  const up = (changePct ?? 0) > 0
  const down = (changePct ?? 0) < 0
  const tone = up ? 'text-up' : down ? 'text-down' : 'text-flat'
  const Icon = up ? TrendingUp : down ? TrendingDown : Minus
  const priceClass = size === 'lg' ? 'text-2xl' : size === 'sm' ? 'text-sm' : 'text-lg'

  return (
    <span className={cn('inline-flex items-baseline gap-2 font-mono', tone)}>
      {price !== undefined && price !== null ? (
        <span className={cn('font-semibold tabular-nums', priceClass)}>{fmtPrice(price)}</span>
      ) : null}
      {changePct !== undefined && changePct !== null ? (
        <span className="inline-flex items-center gap-0.5 text-sm font-medium tabular-nums">
          <Icon className="h-3.5 w-3.5" aria-hidden />
          {fmtPct(changePct)}
        </span>
      ) : null}
    </span>
  )
}
