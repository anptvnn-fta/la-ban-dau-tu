import { useEffect, useState } from 'react'
import { Users } from 'lucide-react'
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { stocksApi, type ForeignFlowBar } from '@/api/stocks'
import { Card, CardLabel } from '@/components/ui/card'
import { fmtNum } from '@/utils/num'
import { VI } from '@/strings/vi'

const css = (name: string, fallback: string) =>
  typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    : fallback

/** Thẻ khối ngoại: biểu đồ mua/bán ròng theo ngày (tỷ VND). */
export function ForeignFlowCard({ code }: { code: string }) {
  const [bars, setBars] = useState<ForeignFlowBar[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let on = true
    setBars(null)
    setError(false)
    stocksApi
      .getForeignFlow(code, 30)
      .then((r) => on && setBars(r.data || []))
      .catch(() => on && setError(true))
    return () => {
      on = false
    }
  }, [code])

  const up = css('--price-up', '#22c55e')
  const down = css('--price-down', '#ef4444')

  const series = (bars || []).map((b) => ({
    date: b.date?.slice(5) ?? '',
    ty: b.netValue != null ? b.netValue / 1e9 : 0,
  }))
  const latest = bars && bars.length ? bars[bars.length - 1] : null

  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <CardLabel icon={<Users className="h-3.5 w-3.5" />}>Khối ngoại · mua/bán ròng (tỷ VND)</CardLabel>
        {latest ? (
          <span className="text-xs text-muted-foreground">
            Room còn: <span className="font-mono text-foreground">{latest.roomPct != null ? `${(latest.roomPct * 100).toFixed(0)}%` : '--'}</span>
          </span>
        ) : null}
      </div>

      {error ? (
        <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">{VI.common.noData}</div>
      ) : bars === null ? (
        <div className="h-[200px] animate-pulse rounded-xl bg-background/40" />
      ) : series.length ? (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={series} margin={{ top: 6, right: 6, left: -12, bottom: 0 }}>
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: css('--neutral-slate', '#94a3b8') }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 10, fill: css('--neutral-slate', '#94a3b8') }} width={40} />
            <ReferenceLine y={0} stroke={css('--border', '#334155')} />
            <Tooltip
              cursor={{ fill: 'transparent' }}
              contentStyle={{ background: css('--card', '#0f172a'), border: `1px solid ${css('--border', '#334155')}`, borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: css('--foreground', '#f8fafc') }}
              formatter={(value) => `${fmtNum(Number(value), 1)} tỷ`}
            />
            <Bar dataKey="ty" radius={[2, 2, 0, 0]}>
              {series.map((d, i) => (
                <Cell key={i} fill={d.ty >= 0 ? up : down} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">{VI.common.noData}</div>
      )}
    </Card>
  )
}
