import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Landmark, RefreshCw, Info, Scale, LineChart as LineChartIcon } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardLabel } from '@/components/ui/card'
import { bondApi } from '@/api/bond'
import type { BondOverview, BondHistory } from '@/types/bond'
import { cn } from '@/lib/utils'
import { VI } from '@/strings/vi'

const css = (name: string, fallback: string) =>
  typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    : fallback

const pct = (v?: number | null) => (v == null ? '--' : `${v}%`)

function RateCard({ label, value, sub, badge }: { label: string; value: string; sub?: string; badge?: string }) {
  return (
    <Card className="glass-hover p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        {badge && <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground">{badge}</span>}
      </div>
      <p className="mt-2 font-mono text-2xl font-bold tabular-nums text-foreground">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </Card>
  )
}

function SpreadRow({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="flex items-center gap-2 text-sm text-muted-foreground">{icon}{label}</span>
      <span className="font-mono text-sm font-semibold tabular-nums text-foreground">{value}</span>
    </div>
  )
}

function US10YChart() {
  const [hist, setHist] = useState<BondHistory | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let on = true
    bondApi.getHistory(365).then((h) => { if (on) setHist(h) }).catch(() => { if (on) setError(true) })
    return () => { on = false }
  }, [])

  const neutral = css('--neutral-slate', '#94a3b8')
  const series = (hist?.points || []).map((p) => ({ date: p.date?.slice(2) ?? '', usYield: p.usYield ?? null }))

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <CardLabel icon={<LineChartIcon className="h-3.5 w-3.5" />}>{VI.bond.chartLabel}</CardLabel>
      </div>
      {error ? (
        <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">{VI.bond.empty}</div>
      ) : hist === null ? (
        <div className="flex h-[240px] flex-col items-center justify-center gap-2">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-transparent" />
          <p className="text-xs text-muted-foreground">{VI.bond.chartLoading}</p>
        </div>
      ) : series.length ? (
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={series} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={css('--border', '#334155')} opacity={0.4} />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: neutral }} interval="preserveStartEnd" minTickGap={28} />
            <YAxis tick={{ fontSize: 10, fill: neutral }} width={40} tickFormatter={(v) => `${v}%`} domain={['auto', 'auto']} />
            <Tooltip
              contentStyle={{ background: css('--card', '#0f172a'), border: `1px solid ${css('--border', '#334155')}`, borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: css('--foreground', '#f8fafc') }}
              formatter={(value) => `${value}%`}
            />
            <Line type="monotone" dataKey="usYield" name="US10Y" stroke={css('--primary', '#3b82f6')} strokeWidth={2} dot={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">{VI.bond.empty}</div>
      )}
    </Card>
  )
}

export default function TraiPhieuPage() {
  const [data, setData] = useState<BondOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    bondApi
      .getOverview()
      .then((d) => { if (!cancelled) setData(d) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => load(), [load])

  const fedRange = data && data.fedLow != null && data.fedHigh != null ? `${data.fedLow}–${data.fedHigh}%` : '--'

  return (
    <>
      <PageHeader
        title={VI.bond.title}
        subtitle={VI.bond.subtitle}
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
          <Landmark className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{VI.bond.empty}</p>
        </Card>
      ) : data ? (
        <div className="space-y-4">
          {/* Mặt bằng lãi suất */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <RateCard label={VI.bond.sbv} value={pct(data.sbvPolicyRate)} sub={VI.bond.sbvSub} />
            <RateCard label={VI.bond.fed} value={fedRange} sub={VI.bond.fedSub} />
            <RateCard label={VI.bond.us10y} value={pct(data.usYield)} sub={VI.bond.us10ySub} />
            <RateCard label={VI.bond.vn10y} value={`~${pct(data.vn10yRef)}`} badge={VI.bond.refBadge} sub={VI.bond.vn10ySub} />
          </div>

          {/* Chênh lệch */}
          <Card className="p-4">
            <CardLabel icon={<Scale className="h-3.5 w-3.5" />}>{VI.bond.spreadLabel}</CardLabel>
            <div className="mt-2 divide-y divide-border/50">
              <SpreadRow icon={<span className="text-up">•</span>} label={VI.bond.spreadSbvFed}
                value={data.spreadSbvFed != null ? `${data.spreadSbvFed > 0 ? '+' : ''}${data.spreadSbvFed} điểm %` : '--'} />
              <SpreadRow icon={<span className="text-primary">•</span>} label={VI.bond.spreadVnUs}
                value={data.spreadVnUs != null ? `${data.spreadVnUs > 0 ? '+' : ''}${data.spreadVnUs} điểm %` : '--'} />
            </div>
          </Card>

          {/* Biểu đồ US10Y */}
          <US10YChart />

          {/* Ghi chú */}
          {data.note && (
            <Card className="p-4">
              <CardLabel icon={<Info className="h-3.5 w-3.5" />}>{VI.bond.noteLabel}</CardLabel>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{data.note}</p>
            </Card>
          )}
        </div>
      ) : null}
    </>
  )
}
