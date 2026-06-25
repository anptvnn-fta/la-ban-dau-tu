import { useEffect, useState, useCallback, useImperativeHandle, forwardRef } from 'react'
import { Clock } from 'lucide-react'
import { historyApi } from '@/api/history'
import type { HistoryItem, DecisionAction } from '@/types/analysis'
import { PriceChange } from '@/components/report/PriceChange'
import { VI } from '@/strings/vi'
import { cn } from '@/lib/utils'

function actionTone(action?: DecisionAction | null): string {
  if (!action) return 'bg-secondary text-secondary-foreground'
  if (action === 'buy' || action === 'add') return 'bg-up/15 text-up'
  if (action === 'sell' || action === 'reduce' || action === 'avoid') return 'bg-down/15 text-down'
  return 'bg-warning/15 text-warning'
}

export interface HistoryListHandle {
  reload: () => void
}

export const HistoryList = forwardRef<HistoryListHandle, {
  onSelect: (recordId: number) => void
  activeId?: number
}>(function HistoryList({ onSelect, activeId }, ref) {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    historyApi
      .getList({ page: 1, limit: 20 })
      .then((r) => setItems(r.items || []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => load(), [load])
  useImperativeHandle(ref, () => ({ reload: load }), [load])

  return (
    <div className="flex h-full flex-col">
      <div className="mb-2 flex items-center gap-2 px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        <Clock className="h-3.5 w-3.5" /> Lịch sử phân tích
      </div>
      <div className="space-y-1.5">
        {loading && !items.length ? (
          <>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-xl bg-card/60" />
            ))}
          </>
        ) : items.length ? (
          items.map((it) => (
            <button
              key={it.id}
              type="button"
              onClick={() => onSelect(it.id)}
              className={cn(
                'w-full rounded-xl border p-3 text-left transition-colors',
                activeId === it.id ? 'border-primary bg-primary/5' : 'border-border bg-card hover:bg-secondary',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate text-sm font-semibold text-foreground">
                  {it.stockName || it.stockCode}
                </span>
                {it.actionLabel ? (
                  <span className={cn('shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-semibold', actionTone(it.action))}>
                    {it.actionLabel}
                  </span>
                ) : null}
              </div>
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className="font-mono text-[11px] text-muted-foreground">{it.stockCode}</span>
                <PriceChange price={it.currentPrice} changePct={it.changePct} size="sm" />
              </div>
            </button>
          ))
        ) : (
          <p className="px-1 py-6 text-center text-sm text-muted-foreground">{VI.common.noData}</p>
        )}
      </div>
    </div>
  )
})
