import { useEffect, useState } from 'react'
import { CandlestickChart as ChartIcon } from 'lucide-react'
import { stocksApi, type OhlcBar } from '@/api/stocks'
import { Card } from '@/components/ui/card'
import { CandlestickChart } from '@/components/charts/CandlestickChart'
import { cn } from '@/lib/utils'
import { VI } from '@/strings/vi'

const LEGEND = [
  { label: 'MA5', color: '#f59e0b' },
  { label: 'MA10', color: '#3b82f6' },
  { label: 'MA20', color: '#a855f7' },
  { label: 'RSI', color: '#22d3ee' },
]

/** Thẻ biểu đồ giá: tự tải nến (kèm chỉ báo) và hiển thị, có bật/tắt chỉ báo. */
export function PriceChartCard({ code }: { code: string }) {
  const [bars, setBars] = useState<OhlcBar[] | null>(null)
  const [error, setError] = useState(false)
  const [showInd, setShowInd] = useState(true)

  useEffect(() => {
    let on = true
    setBars(null)
    setError(false)
    stocksApi
      .getHistory(code, 160, 'daily', true)
      .then((r) => on && setBars(r.data || []))
      .catch(() => on && setError(true))
    return () => {
      on = false
    }
  }, [code])

  return (
    <Card className="p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <ChartIcon className="h-4 w-4" />
          </span>
          <h3 className="text-base font-semibold text-foreground">Biểu đồ giá</h3>
        </div>
        <div className="flex items-center gap-3">
          {showInd ? (
            <div className="hidden items-center gap-2.5 sm:flex">
              {LEGEND.map((l) => (
                <span key={l.label} className="flex items-center gap-1 text-[11px] text-muted-foreground">
                  <span className="inline-block h-0.5 w-3 rounded" style={{ background: l.color }} />
                  {l.label}
                </span>
              ))}
            </div>
          ) : null}
          <button
            type="button"
            onClick={() => setShowInd((v) => !v)}
            aria-pressed={showInd}
            className={cn(
              'rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              showInd ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:bg-secondary',
            )}
          >
            Chỉ báo
          </button>
        </div>
      </div>

      {error ? (
        <div className="flex h-[340px] items-center justify-center text-sm text-muted-foreground">{VI.common.noData}</div>
      ) : bars === null ? (
        <div className="h-[340px] animate-pulse rounded-xl bg-background/40" />
      ) : bars.length ? (
        <CandlestickChart bars={bars} showIndicators={showInd} />
      ) : (
        <div className="flex h-[340px] items-center justify-center text-sm text-muted-foreground">{VI.common.noData}</div>
      )}
    </Card>
  )
}
