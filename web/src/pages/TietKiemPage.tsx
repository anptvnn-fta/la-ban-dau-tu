import { useCallback, useEffect, useState } from 'react'
import { PiggyBank, RefreshCw, Landmark, Trophy } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardLabel } from '@/components/ui/card'
import { savingsApi } from '@/api/savings'
import type { SavingsOverview } from '@/types/savings'
import { cn } from '@/lib/utils'
import { VI } from '@/strings/vi'

const pct = (v?: number | null) => (v == null ? '--' : `${v}%`)
const termLabel = (m: number) => `${m} tháng`

export default function TietKiemPage() {
  const [data, setData] = useState<SavingsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    savingsApi
      .getOverview()
      .then((d) => { if (!cancelled) setData(d) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => load(), [load])

  // Lãi suất cao nhất theo từng kỳ hạn (để tô đậm trong bảng).
  const maxPerTerm = (data?.terms || []).map((t) => {
    const b = data?.best.find((x) => x.term === t)
    return b?.rate ?? null
  })

  return (
    <>
      <PageHeader
        title={VI.savings.title}
        subtitle={VI.savings.subtitle}
        actions={
          <button
            type="button"
            aria-label={VI.common.refresh}
            onClick={() => load()}
            disabled={loading}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
          >
            <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
          </button>
        }
      />

      {loading && !data ? (
        <div className="h-48 animate-pulse rounded-xl bg-secondary/50" />
      ) : error && !data ? (
        <Card className="flex h-48 flex-col items-center justify-center gap-3 text-center">
          <PiggyBank className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{VI.savings.empty}</p>
        </Card>
      ) : data ? (
        <div className="space-y-4">
          {data.dataWarning && (
            <Card className="border-amber-500/30 bg-amber-500/5 p-3">
              <p className="text-sm text-amber-600 dark:text-amber-400">{data.dataWarning}</p>
            </Card>
          )}

          {/* Lãi suất tốt nhất theo kỳ hạn */}
          <Card className="glass p-4">
            <CardLabel icon={<Trophy className="h-3.5 w-3.5" />}>{VI.savings.bestLabel}</CardLabel>
            <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-5">
              {data.best.map((b) => (
                <div key={b.term} className="rounded-lg border border-border bg-card/50 p-3">
                  <p className="text-xs text-muted-foreground">{termLabel(b.term)}</p>
                  <p className="mt-1 font-mono text-2xl font-bold tabular-nums text-up">{pct(b.rate)}</p>
                  <p className="truncate text-xs text-muted-foreground" title={b.bank}>{b.bank}</p>
                </div>
              ))}
            </div>
          </Card>

          {/* Bảng ngân hàng × kỳ hạn */}
          <Card className="p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <CardLabel icon={<Landmark className="h-3.5 w-3.5" />}>{VI.savings.tableLabel}</CardLabel>
              <span className="text-xs text-muted-foreground">{data.banks.length} ngân hàng · %/năm</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground">
                    <th className="py-2 pr-3 text-left font-medium">{VI.savings.bank}</th>
                    {data.terms.map((t) => (
                      <th key={t} className="py-2 px-2 text-right font-medium">{termLabel(t)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.banks.map((b) => (
                    <tr key={b.symbol || b.name} className="border-b border-border/50 last:border-0">
                      <td className="py-2 pr-3 text-foreground">{b.name}</td>
                      {b.rates.map((r, i) => {
                        const isBest = r != null && maxPerTerm[i] != null && r === maxPerTerm[i]
                        return (
                          <td
                            key={i}
                            className={cn(
                              'py-2 px-2 text-right font-mono tabular-nums',
                              isBest ? 'font-bold text-up' : 'text-foreground',
                            )}
                          >
                            {r == null ? '–' : `${r}%`}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Bối cảnh SBV */}
          {data.note && (
            <Card className="p-4">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm text-muted-foreground">{VI.savings.sbvLabel}</span>
                <span className="font-mono text-lg font-bold text-foreground">{pct(data.sbvPolicyRate)}</span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{data.note}</p>
            </Card>
          )}
        </div>
      ) : null}
    </>
  )
}
