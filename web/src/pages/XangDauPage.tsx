import { useCallback, useEffect, useState } from 'react'
import { Fuel, Globe, RefreshCw, Info, CalendarClock, LineChart as LineChartIcon } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardLabel } from '@/components/ui/card'
import { petrolApi } from '@/api/petrol'
import type { PetrolOverview, PetrolHistory } from '@/types/petrol'
import { cn } from '@/lib/utils'
import { VI } from '@/strings/vi'

const css = (name: string, fallback: string) =>
  typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    : fallback

const dong = (v?: number | null) => (v == null ? '--' : `${Math.round(v).toLocaleString('vi-VN')} đ`)
const dShort = (v?: number | null) => (v == null ? '' : `${(v / 1000).toLocaleString('vi-VN', { maximumFractionDigits: 1 })}k`)
const dateVN = (s?: string | null) =>
  s ? new Date(s).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '--'

/** Tông màu: giá giảm = xanh (lợi cho người dùng), tăng = đỏ. */
function changeTone(ch?: number | null): string {
  if (ch == null || ch === 0) return 'text-muted-foreground'
  return ch < 0 ? 'text-up' : 'text-down'
}

const PETROL_RANGES = [
  { label: '1 năm', days: 365 },
  { label: '3 năm', days: 1095 },
  { label: 'Từ 2018', days: 3000 },
]

function PetrolChart() {
  const [days, setDays] = useState(365)
  const [hist, setHist] = useState<PetrolHistory | null>(null)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let on = true
    setLoading(true)
    setError(false)
    petrolApi
      .getHistory(days)
      .then((h) => { if (on) setHist(h) })
      .catch(() => { if (on) setError(true) })
      .finally(() => { if (on) setLoading(false) })
    return () => { on = false }
  }, [days])

  const neutral = css('--neutral-slate', '#94a3b8')
  const series = (hist?.points || []).map((p) => ({
    date: p.date?.slice(2) ?? '',
    e5: p.e5 ?? null,
    ron95: p.ron95 ?? null,
    brent: p.brent ?? null,
  }))

  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <CardLabel icon={<LineChartIcon className="h-3.5 w-3.5" />}>{VI.petrol.chartLabel}</CardLabel>
        <div className="flex gap-1">
          {PETROL_RANGES.map((r) => (
            <button
              key={r.days}
              type="button"
              onClick={() => setDays(r.days)}
              className={cn(
                'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                days === r.days ? 'bg-primary text-primary-foreground' : 'bg-secondary text-muted-foreground hover:text-foreground',
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>
      {error ? (
        <div className="flex h-[280px] items-center justify-center text-sm text-muted-foreground">{VI.petrol.empty}</div>
      ) : loading && !hist ? (
        <div className="flex h-[280px] flex-col items-center justify-center gap-2">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-transparent" />
          <p className="text-xs text-muted-foreground">{VI.petrol.chartLoading}</p>
        </div>
      ) : series.length ? (
        <>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={series} margin={{ top: 6, right: 6, left: 4, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={css('--border', '#334155')} opacity={0.4} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: neutral }} interval="preserveStartEnd" minTickGap={28} />
              <YAxis yAxisId="vn" tick={{ fontSize: 10, fill: neutral }} width={42} tickFormatter={(v) => dShort(Number(v))} domain={['auto', 'auto']} />
              <YAxis yAxisId="oil" orientation="right" tick={{ fontSize: 10, fill: neutral }} width={36} domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ background: css('--card', '#0f172a'), border: `1px solid ${css('--border', '#334155')}`, borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: css('--foreground', '#f8fafc') }}
                formatter={(value, name) => (name === VI.petrol.lineBrent ? `${value} USD/thùng` : dong(Number(value)))}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line yAxisId="vn" type="monotone" dataKey="e5" name={VI.petrol.lineE5} stroke={css('--primary', '#3b82f6')} strokeWidth={2} dot={false} connectNulls />
              <Line yAxisId="vn" type="monotone" dataKey="ron95" name={VI.petrol.lineRon95} stroke="#f59e0b" strokeWidth={2} dot={false} connectNulls />
              <Line yAxisId="oil" type="monotone" dataKey="brent" name={VI.petrol.lineBrent} stroke={css('--neutral-slate', '#94a3b8')} strokeWidth={1.5} strokeDasharray="4 3" dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
          <p className="mt-2 text-xs text-muted-foreground">{VI.petrol.chartNote}</p>
        </>
      ) : (
        <div className="flex h-[280px] items-center justify-center text-sm text-muted-foreground">{VI.petrol.empty}</div>
      )}
    </Card>
  )
}

export default function XangDauPage() {
  const [data, setData] = useState<PetrolOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    petrolApi
      .getOverview()
      .then((d) => { if (!cancelled) setData(d) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => load(), [load])

  return (
    <>
      <PageHeader
        title={VI.petrol.title}
        subtitle={VI.petrol.subtitle}
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
          <Fuel className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{VI.petrol.empty}</p>
        </Card>
      ) : data ? (
        <div className="space-y-4">
          {data.dataWarning && (
            <Card className="border-amber-500/30 bg-amber-500/5 p-3">
              <p className="text-sm text-amber-600 dark:text-amber-400">{data.dataWarning}</p>
            </Card>
          )}

          {/* Giá hiện tại theo mặt hàng */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {data.fuels.map((f) => (
              <Card key={f.code} className="glass-hover p-4">
                <p className="text-xs font-medium text-muted-foreground">{f.name}</p>
                <p className="mt-2 font-mono text-xl font-bold tabular-nums text-foreground">{dong(f.price)}</p>
                <p className={cn('mt-1 font-mono text-xs tabular-nums', changeTone(f.change))}>
                  {f.change != null
                    ? `${f.change > 0 ? '+' : ''}${dong(f.change)}${f.changePct != null ? ` · ${f.changePct}%` : ''}`
                    : (f.price == null ? VI.petrol.discontinued : '—')}
                </p>
              </Card>
            ))}
          </div>

          {/* Kỳ điều hành + dầu thế giới */}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Card className="p-4">
              <CardLabel icon={<CalendarClock className="h-3.5 w-3.5" />}>{VI.petrol.cycleLabel}</CardLabel>
              <div className="mt-3 space-y-1.5 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">{VI.petrol.effective}</span><span className="font-medium text-foreground">{dateVN(data.effectiveDate)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">{VI.petrol.nextAdj}</span><span className="font-medium text-primary">{dateVN(data.nextAdjustment)}</span></div>
              </div>
            </Card>
            <Card className="p-4">
              <CardLabel icon={<Globe className="h-3.5 w-3.5" />}>{VI.petrol.world}</CardLabel>
              <div className="mt-3 space-y-1.5 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Brent</span><span className="font-mono font-semibold text-foreground">{data.brentUsd != null ? `${data.brentUsd} $/thùng` : '--'}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">WTI</span><span className="font-mono font-semibold text-foreground">{data.wtiUsd != null ? `${data.wtiUsd} $/thùng` : '--'}</span></div>
              </div>
            </Card>
          </div>

          {/* Biểu đồ VN vs dầu thế giới */}
          <PetrolChart />

          {/* Cơ chế điều hành */}
          {data.cycleNote && (
            <Card className="p-4">
              <CardLabel icon={<Info className="h-3.5 w-3.5" />}>{VI.petrol.mechLabel}</CardLabel>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{data.cycleNote}</p>
            </Card>
          )}
        </div>
      ) : null}
    </>
  )
}
