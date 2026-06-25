import { useMemo, useRef, useState } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { useStockIndex } from '@/hooks/useStockIndex'
import { searchStocks } from '@/utils/searchStocks'
import { getPopularStocks } from '@/utils/stockIndexLoader'
import type { StockIndexItem, StockSuggestion } from '@/types/stockIndex'
import { VI } from '@/strings/vi'
import { cn } from '@/lib/utils'

export interface SelectedStock {
  code: string
  name: string
}

export function StockSearch({
  onAnalyze,
  loading,
}: {
  onAnalyze: (stock: SelectedStock) => void
  loading?: boolean
}) {
  const { items, loading: indexLoading } = useStockIndex()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const suggestions: StockSuggestion[] = useMemo(() => {
    const q = query.trim()
    if (!q) return []
    return searchStocks(q, items, { limit: 8 })
  }, [query, items])

  const popular: StockIndexItem[] = useMemo(
    () => (query.trim() ? [] : getPopularStocks(items, 8)),
    [query, items],
  )

  const submit = (code: string, name: string) => {
    if (!code) return
    setOpen(false)
    setQuery('')
    onAnalyze({ code, name })
  }

  const onSubmitRaw = () => {
    const q = query.trim().toUpperCase()
    if (!q) return
    if (suggestions[active]) {
      submit(suggestions[active].canonicalCode, suggestions[active].nameZh)
    } else {
      // Cho phép gõ thẳng mã, ví dụ "VCB" → "VCB.VN"
      const code = q.includes('.') ? q : `${q}.VN`
      submit(code, q)
    }
  }

  const showDrop = open && (suggestions.length > 0 || popular.length > 0)

  return (
    <div className="relative">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setOpen(true)
              setActive(0)
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => window.setTimeout(() => setOpen(false), 150)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setActive((a) => Math.min(a + 1, suggestions.length - 1))
              } else if (e.key === 'ArrowUp') {
                e.preventDefault()
                setActive((a) => Math.max(a - 1, 0))
              } else if (e.key === 'Enter') {
                e.preventDefault()
                onSubmitRaw()
              } else if (e.key === 'Escape') {
                setOpen(false)
              }
            }}
            placeholder={VI.home.searchPlaceholder}
            aria-label={VI.home.searchPlaceholder}
            className="h-12 w-full rounded-xl border border-input bg-card pl-10 pr-3 text-[15px] text-foreground placeholder:text-muted-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <button
          type="button"
          onClick={onSubmitRaw}
          disabled={loading || !query.trim()}
          className="inline-flex h-12 shrink-0 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          {VI.home.analyzeBtn}
        </button>
      </div>

      {showDrop ? (
        <div className="absolute z-30 mt-2 w-full overflow-hidden rounded-xl border border-border bg-popover shadow-xl">
          {indexLoading ? (
            <div className="px-4 py-3 text-sm text-muted-foreground">{VI.common.loading}</div>
          ) : null}
          {(suggestions.length ? suggestions : popular.map((p) => ({
            canonicalCode: p.canonicalCode,
            displayCode: p.displayCode,
            nameZh: p.nameZh,
          }))).map((s, i) => (
            <button
              key={s.canonicalCode}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => submit(s.canonicalCode, s.nameZh)}
              className={cn(
                'flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition-colors',
                suggestions.length && i === active ? 'bg-accent' : 'hover:bg-secondary',
              )}
            >
              <span className="min-w-0">
                <span className="font-mono text-sm font-semibold text-foreground">{s.displayCode}</span>
                <span className="ml-2 truncate text-sm text-muted-foreground">{s.nameZh}</span>
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
