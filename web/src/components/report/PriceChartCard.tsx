import { useEffect, useState } from 'react'
import { CandlestickChart as ChartIcon } from 'lucide-react'
import { stocksApi, type OhlcBar } from '@/api/stocks'
import { Card } from '@/components/ui/card'
import { CandlestickChart } from '@/components/charts/CandlestickChart'
import { VI } from '@/strings/vi'

/** Thẻ biểu đồ giá: tự tải dữ liệu nến cho một mã và hiển thị. */
export function PriceChartCard({ code }: { code: string }) {
  const [bars, setBars] = useState<OhlcBar[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let on = true
    setBars(null)
    setError(false)
    stocksApi
      .getHistory(code, 160)
      .then((r) => {
        if (on) setBars(r.data || [])
      })
      .catch(() => on && setError(true))
    return () => {
      on = false
    }
  }, [code])

  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <ChartIcon className="h-4 w-4" />
        </span>
        <h3 className="text-base font-semibold text-foreground">Biểu đồ giá</h3>
      </div>
      {error ? (
        <div className="flex h-[340px] items-center justify-center text-sm text-muted-foreground">{VI.common.noData}</div>
      ) : bars === null ? (
        <div className="h-[340px] animate-pulse rounded-xl bg-background/40" />
      ) : bars.length ? (
        <CandlestickChart bars={bars} />
      ) : (
        <div className="flex h-[340px] items-center justify-center text-sm text-muted-foreground">{VI.common.noData}</div>
      )}
    </Card>
  )
}
