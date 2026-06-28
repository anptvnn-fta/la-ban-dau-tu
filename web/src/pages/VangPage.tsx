import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Coins, Globe, ArrowLeftRight, RefreshCw, Info, TrendingUp, LineChart as LineChartIcon, Table as TableIcon } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardLabel } from '@/components/ui/card'
import { goldApi } from '@/api/gold'
import type { GoldOverview, GoldHistory } from '@/types/gold'
import { cn } from '@/lib/utils'
import { VI } from '@/strings/vi'

const css = (name: string, fallback: string) =>
  typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    : fallback

/** Định dạng VND đầy đủ (vd 147.000.000 đ). */
function vnd(v?: number | null): string {
  if (v == null) return '--'
  return `${Math.round(v).toLocaleString('vi-VN')} đ`
}

/** Rút gọn VND cho trục/tooltip biểu đồ (vd 147,0tr). */
function vndShort(v?: number | null): string {
  if (v == null) return '--'
  return `${(v / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 1 })}tr`
}

const GOLD_RANGES = [
  { label: '3 tháng', days: 90, step: 7 },
  { label: '6 tháng', days: 180, step: 14 },
  { label: '1 năm', days: 365, step: 30 },
]

/** Biểu đồ lịch sử: giá SJC trong nước vs vàng thế giới quy đổi (VND/lượng). */
function GoldChart() {
  const [days, setDays] = useState(180)
  const [hist, setHist] = useState<GoldHistory | null>(null)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let on = true
    const range = GOLD_RANGES.find((r) => r.days === days) ?? GOLD_RANGES[1]
    setLoading(true)
    setError(false)
    goldApi
      .getHistory(range.days, range.step)
      .then((h) => { if (on) setHist(h) })
      .catch(() => { if (on) setError(true) })
      .finally(() => { if (on) setLoading(false) })
    return () => { on = false }
  }, [days])

  const up = css('--price-up', '#22c55e')
  const neutral = css('--neutral-slate', '#94a3b8')
  const series = (hist?.points || []).map((p) => ({
    date: p.date?.slice(5).replace('-', '/') ?? '',
    sjc: p.sjc ?? null,
    world: p.world ?? null,
  }))

  // Nhận định hiện tại so với trung bình kỳ.
  const cur = hist?.premiumCurrentPct
  const avg = hist?.premiumAvgPct
  let verdict = ''
  if (cur != null && avg != null) {
    const d = cur - avg
    verdict = Math.abs(d) < 1 ? 'ngang mức trung bình'
      : d > 0 ? `cao hơn trung bình ${d.toFixed(1)} điểm %`
      : `thấp hơn trung bình ${Math.abs(d).toFixed(1)} điểm %`
  }

  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <CardLabel icon={<LineChartIcon className="h-3.5 w-3.5" />}>{VI.gold.chartLabel}</CardLabel>
        <div className="flex gap-1">
          {GOLD_RANGES.map((r) => (
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
        <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">{VI.gold.empty}</div>
      ) : loading && !hist ? (
        <div className="flex h-[260px] flex-col items-center justify-center gap-2">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-transparent" />
          <p className="text-xs text-muted-foreground">{VI.gold.chartLoading}</p>
        </div>
      ) : series.length ? (
        <>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={series} margin={{ top: 6, right: 8, left: 4, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={css('--border', '#334155')} opacity={0.4} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: neutral }} interval="preserveStartEnd" minTickGap={24} />
              <YAxis tick={{ fontSize: 10, fill: neutral }} width={48} tickFormatter={(v) => vndShort(Number(v))} domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ background: css('--card', '#0f172a'), border: `1px solid ${css('--border', '#334155')}`, borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: css('--foreground', '#f8fafc') }}
                formatter={(value) => vnd(Number(value))}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="sjc" name={VI.gold.lineSjc} stroke={css('--primary', '#3b82f6')} strokeWidth={2} dot={false} connectNulls />
              <Line type="monotone" dataKey="world" name={VI.gold.lineWorld} stroke={up} strokeWidth={2} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
          {avg != null && (
            <p className="mt-2 text-xs text-muted-foreground">
              {VI.gold.premiumBand}: <span className="font-mono text-foreground">{avg}%</span>
              {hist?.premiumMinPct != null && hist?.premiumMaxPct != null && (
                <> · dao động {hist.premiumMinPct}–{hist.premiumMaxPct}%</>
              )}
              {verdict && <> · hiện {verdict}</>}
            </p>
          )}
        </>
      ) : (
        <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">{VI.gold.empty}</div>
      )}
    </Card>
  )
}

/** Tông màu theo mức premium: cao = cảnh báo (đắt). */
function premiumTone(pct?: number | null): string {
  if (pct == null) return 'text-muted-foreground'
  if (pct < 5) return 'text-up'
  if (pct < 10) return 'text-amber-500'
  return 'text-down'
}

function StatCard({
  icon, label, children,
}: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <Card className="glass-hover p-4">
      <CardLabel icon={icon}>{label}</CardLabel>
      <div className="mt-3 space-y-1.5">{children}</div>
    </Card>
  )
}

function Row({ k, v, mono = true, tone }: { k: string; v: string; mono?: boolean; tone?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-sm text-muted-foreground">{k}</span>
      <span className={cn('text-sm font-semibold tabular-nums', mono && 'font-mono', tone ?? 'text-foreground')}>{v}</span>
    </div>
  )
}

export default function VangPage() {
  const [data, setData] = useState<GoldOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    goldApi
      .getOverview()
      .then((d) => { if (!cancelled) setData(d) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => load(), [load])

  const updatedAt = data?.generatedAt
    ? new Date(data.generatedAt).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    : null

  const tone = premiumTone(data?.premiumPct)

  return (
    <>
      <PageHeader
        title={VI.gold.title}
        subtitle={VI.gold.subtitle}
        actions={
          <div className="flex items-center gap-2">
            {updatedAt && (
              <span className="hidden text-xs text-muted-foreground sm:inline">{VI.gold.updated} {updatedAt}</span>
            )}
            <button
              type="button"
              aria-label={VI.common.refresh}
              onClick={() => load()}
              disabled={loading}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            </button>
          </div>
        }
      />

      {loading && !data ? (
        <div className="h-48 animate-pulse rounded-xl bg-secondary/50" />
      ) : error && !data ? (
        <Card className="flex h-48 flex-col items-center justify-center gap-3 text-center">
          <Coins className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{VI.gold.empty}</p>
        </Card>
      ) : data ? (
        <div className="space-y-4">
          {data.dataWarning && (
            <Card className="border-amber-500/30 bg-amber-500/5 p-3">
              <p className="text-sm text-amber-600 dark:text-amber-400">{data.dataWarning}</p>
            </Card>
          )}

          {/* ── Hero: chênh lệch SJC vs thế giới ── */}
          <Card className="glass p-5">
            <CardLabel icon={<TrendingUp className="h-3.5 w-3.5" />}>{VI.gold.premiumLabel}</CardLabel>
            <div className="mt-3 flex flex-wrap items-end gap-x-4 gap-y-1">
              <span className={cn('font-mono text-3xl font-bold tabular-nums sm:text-4xl', tone)}>
                {data.premiumVnd != null ? vnd(data.premiumVnd) : '--'}
              </span>
              <span className={cn('font-mono text-xl font-semibold tabular-nums', tone)}>
                {data.premiumPct != null ? `${data.premiumPct > 0 ? '+' : ''}${data.premiumPct}%` : ''}
              </span>
              <span className="text-xs text-muted-foreground">/ lượng so với giá thế giới quy đổi</span>
            </div>
            {data.assessment && <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{data.assessment}</p>}
          </Card>

          {/* ── 3 thẻ: SJC / thế giới / tỷ giá ── */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <StatCard icon={<Coins className="h-3.5 w-3.5" />} label={`${VI.gold.sjc} · ${data.sjcBranch ?? ''}`}>
              <Row k={VI.gold.buy} v={vnd(data.sjcBuy)} />
              <Row k={VI.gold.sell} v={vnd(data.sjcSell)} />
              <Row k={VI.gold.spread} v={vnd(data.bidAskSpread)} tone="text-amber-500" />
              <p className="pt-1 text-xs text-muted-foreground">{VI.gold.perLuongNote}</p>
            </StatCard>

            <StatCard icon={<Globe className="h-3.5 w-3.5" />} label={VI.gold.world}>
              <Row k={VI.gold.worldOz} v={data.worldUsdOz != null ? `${data.worldUsdOz.toLocaleString('vi-VN')} $/oz` : '--'} />
              <Row k={VI.gold.worldPerLuong} v={vnd(data.worldPerLuongVnd)} />
              <p className="pt-1 text-xs text-muted-foreground">{VI.gold.source}: {data.worldSource ?? '--'}</p>
            </StatCard>

            <StatCard icon={<ArrowLeftRight className="h-3.5 w-3.5" />} label={VI.gold.fx}>
              <Row k="USD/VND" v={data.usdVnd != null ? data.usdVnd.toLocaleString('vi-VN') : '--'} />
              <p className="pt-1 text-xs text-muted-foreground">{VI.gold.fxNote}</p>
            </StatCard>
          </div>

          {/* ── Biểu đồ lịch sử SJC vs thế giới ── */}
          <GoldChart />

          {/* ── Bảng các loại vàng trong nước ── */}
          {data.goldTypes && data.goldTypes.length > 0 && (
            <Card className="p-4">
              <CardLabel icon={<TableIcon className="h-3.5 w-3.5" />}>{VI.gold.typesLabel}</CardLabel>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs text-muted-foreground">
                      <th className="py-2 pr-3 text-left font-medium">{VI.gold.typeName}</th>
                      <th className="py-2 text-right font-medium">{VI.gold.buy}</th>
                      <th className="py-2 pl-3 text-right font-medium">{VI.gold.sell}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.goldTypes.map((t, i) => (
                      <tr key={i} className="border-b border-border/50 last:border-0">
                        <td className="py-2 pr-3 text-foreground">{t.name}</td>
                        <td className="py-2 text-right font-mono tabular-nums text-foreground">{vnd(t.buy)}</td>
                        <td className="py-2 pl-3 text-right font-mono tabular-nums text-foreground">{vnd(t.sell)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{VI.gold.typesNote}</p>
            </Card>
          )}

          {/* ── Cách tính ── */}
          <Card className="p-4">
            <CardLabel icon={<Info className="h-3.5 w-3.5" />}>{VI.gold.howLabel}</CardLabel>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              {VI.gold.howBody}
            </p>
            <p className="mt-2 font-mono text-xs text-muted-foreground">
              Giá TG quy đổi = giá($/oz) × 1,20565 × USD/VND · Chênh lệch = giá SJC bán − giá TG quy đổi
            </p>
          </Card>
        </div>
      ) : null}
    </>
  )
}
