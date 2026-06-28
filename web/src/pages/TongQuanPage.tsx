import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowDown, ArrowUp, BarChart3, Layers, Minus, RefreshCw, TrendingDown, TrendingUp,
  Coins, Fuel, PiggyBank, Landmark, ChevronRight, Compass,
} from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardLabel } from '@/components/ui/card'
import { marketApi } from '@/api/market'
import { goldApi } from '@/api/gold'
import { petrolApi } from '@/api/petrol'
import { savingsApi } from '@/api/savings'
import { bondApi } from '@/api/bond'
import type { MarketIndex, MarketMover, MarketOverview, MarketSector } from '@/types/market'
import { fmtPrice, fmtPct, fmtCompact, priceToneClass } from '@/utils/num'
import { cn } from '@/lib/utils'
import { VI } from '@/strings/vi'

// ── tiện ích màu ──────────────────────────────────────────
function DirIcon({ pct, className }: { pct?: number | null; className?: string }) {
  if (pct == null || pct === 0) return <Minus className={className} />
  return pct > 0 ? <ArrowUp className={className} /> : <ArrowDown className={className} />
}

function sectorTone(pct?: number | null): string {
  if (pct == null || pct === 0) return 'bg-secondary text-muted-foreground'
  if (pct > 0) return pct >= 1 ? 'bg-up/20 text-up' : 'bg-up/10 text-up'
  return pct <= -1 ? 'bg-down/20 text-down' : 'bg-down/10 text-down'
}

// ── thẻ chỉ số ────────────────────────────────────────────
function IndexCard({ idx }: { idx: MarketIndex }) {
  const tone = priceToneClass(idx.changePct)
  return (
    <Card className="glass-hover p-4">
      <div className="flex items-center justify-between">
        <span className="font-heading text-sm font-semibold text-foreground">{idx.name || idx.code}</span>
        <DirIcon pct={idx.changePct} className={cn('h-4 w-4', tone)} />
      </div>
      <p className="mt-2 font-mono text-2xl font-bold tabular-nums text-foreground">{fmtPrice(idx.current)}</p>
      <p className={cn('mt-1 font-mono text-sm tabular-nums', tone)}>
        {idx.change != null ? `${idx.change > 0 ? '+' : ''}${fmtPrice(idx.change)}` : '--'} · {fmtPct(idx.changePct)}
      </p>
    </Card>
  )
}

// ── thanh độ rộng ─────────────────────────────────────────
function BreadthBar({ ov }: { ov: MarketOverview }) {
  const b = ov.breadth
  if (!b) return null
  const total = Math.max(1, b.advancers + b.decliners + b.unchanged)
  const advW = (b.advancers / total) * 100
  const unchW = (b.unchanged / total) * 100
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <CardLabel icon={<BarChart3 className="h-3.5 w-3.5" />}>{VI.market.breadth}</CardLabel>
        {b.totalValue != null && (
          <span className="text-xs text-muted-foreground">
            {VI.market.totalValue}: <span className="font-mono text-foreground">{fmtCompact(b.totalValue)}</span>
          </span>
        )}
      </div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-secondary">
        <div className="h-full bg-up" style={{ width: `${advW}%` }} />
        <div className="h-full bg-muted-foreground/30" style={{ width: `${unchW}%` }} />
        {/* Thanh "giảm" lấp phần còn lại để không bị kẽ hở do làm tròn */}
        {b.decliners > 0 && <div className="h-full flex-1 bg-down" />}
      </div>
      <div className="mt-2 flex items-center justify-between text-xs">
        <span className="flex items-center gap-1 font-medium text-up"><ArrowUp className="h-3.5 w-3.5" />{b.advancers} {VI.market.advancers.toLowerCase()}</span>
        <span className="text-muted-foreground">{b.unchanged} {VI.market.unchanged.toLowerCase()}</span>
        <span className="flex items-center gap-1 font-medium text-down">{b.decliners} {VI.market.decliners.toLowerCase()}<ArrowDown className="h-3.5 w-3.5" /></span>
      </div>
    </Card>
  )
}

// ── ô ngành (heatmap) ─────────────────────────────────────
function SectorTile({ s }: { s: MarketSector }) {
  return (
    <div className={cn('flex flex-col gap-0.5 rounded-xl px-3 py-2.5', sectorTone(s.changePct))}>
      <span className="truncate text-sm font-medium">{s.name}</span>
      <span className="font-mono text-sm font-semibold tabular-nums">{fmtPct(s.changePct)}</span>
      <span className="text-[11px] opacity-70">{s.count} mã</span>
    </div>
  )
}

// ── hàng top mover ────────────────────────────────────────
function MoverRow({ m }: { m: MarketMover }) {
  const tone = priceToneClass(m.changePct)
  return (
    <div className="flex items-center justify-between gap-2 border-b border-border/60 py-2 last:border-b-0">
      <div className="min-w-0">
        <span className="font-mono text-sm font-semibold text-foreground">{m.code}</span>
        {m.name && <span className="ml-2 truncate text-xs text-muted-foreground">{m.name}</span>}
      </div>
      <div className="flex items-center gap-3 shrink-0 text-right">
        <span className="font-mono text-sm tabular-nums text-foreground">{fmtPrice(m.price)}</span>
        <span className={cn('flex w-16 items-center justify-end gap-0.5 font-mono text-sm font-semibold tabular-nums', tone)}>
          <DirIcon pct={m.changePct} className="h-3.5 w-3.5" />{fmtPct(m.changePct)}
        </span>
      </div>
    </div>
  )
}

function MoverCard({ title, icon, movers, empty }: { title: string; icon: React.ReactNode; movers: MarketMover[]; empty: string }) {
  return (
    <Card className="p-4">
      <CardLabel icon={icon}>{title}</CardLabel>
      <div className="mt-2">
        {movers.length ? movers.map((m) => <MoverRow key={m.code} m={m} />) : (
          <p className="py-6 text-center text-sm text-muted-foreground">{empty}</p>
        )}
      </div>
    </Card>
  )
}

// ── skeleton ──────────────────────────────────────────────
function Skeleton() {
  const block = 'animate-pulse rounded-2xl border border-border bg-card/60'
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <div key={i} className={cn(block, 'h-28')} />)}
      </div>
      <div className={cn(block, 'h-24')} />
      <div className={cn(block, 'h-40')} />
    </div>
  )
}

// ── dải toàn cảnh đa tài sản (vàng / xăng dầu / tiết kiệm / trái phiếu) ──
interface AssetTile { to: string; icon: ReactNode; iconCls: string; label: string; value: string; sub?: string }

function MultiAssetSummary() {
  const [tiles, setTiles] = useState<AssetTile[] | null>(null)

  useEffect(() => {
    let on = true
    Promise.allSettled([
      goldApi.getOverview(), petrolApi.getOverview(), savingsApi.getOverview(), bondApi.getOverview(),
    ]).then(([g, p, s, b]) => {
      if (!on) return
      const out: AssetTile[] = []
      if (g.status === 'fulfilled' && g.value.sjcSell != null) {
        out.push({ to: '/vang', icon: <Coins className="h-[18px] w-[18px]" />, iconCls: 'text-amber-500', label: 'Vàng SJC (bán)',
          value: fmtCompact(g.value.sjcSell), sub: g.value.premiumPct != null ? `Chênh thế giới ${g.value.premiumPct}%` : 'VND/lượng' })
      }
      if (p.status === 'fulfilled') {
        const ron = p.value.fuels?.find((f) => /RON\s?95/i.test(f.name)) ?? p.value.fuels?.[0]
        if (ron?.price != null) {
          out.push({ to: '/xang-dau', icon: <Fuel className="h-[18px] w-[18px]" />, iconCls: 'text-rose-500', label: ron.name || 'Xăng RON 95',
            value: `${ron.price.toLocaleString('vi-VN')} đ/l`, sub: ron.changePct != null ? `${ron.changePct > 0 ? '+' : ''}${ron.changePct}% kỳ trước` : undefined })
        }
      }
      if (s.status === 'fulfilled') {
        const best = s.value.best?.find((x) => x.term === 12) ?? s.value.best?.[0]
        if (best) {
          out.push({ to: '/tiet-kiem', icon: <PiggyBank className="h-[18px] w-[18px]" />, iconCls: 'text-emerald-500',
            label: best.term ? `Tiết kiệm ${best.term} tháng` : 'Tiết kiệm tốt nhất', value: `${best.rate}%/năm`, sub: best.bank })
        }
      }
      if (b.status === 'fulfilled' && b.value.usYield != null) {
        out.push({ to: '/trai-phieu', icon: <Landmark className="h-[18px] w-[18px]" />, iconCls: 'text-violet-500', label: 'Trái phiếu Mỹ 10 năm',
          value: `${b.value.usYield}%`, sub: b.value.sbvPolicyRate != null ? `SBV ${b.value.sbvPolicyRate}%/năm` : undefined })
      }
      setTiles(out)
    }).catch(() => { if (on) setTiles([]) })
    return () => { on = false }
  }, [])

  if (tiles && tiles.length === 0) return null

  return (
    <Card className="p-4">
      <CardLabel icon={<Compass className="h-3.5 w-3.5" />}>{VI.market.multiAsset}</CardLabel>
      <div className="mt-2 grid grid-cols-2 gap-2 lg:grid-cols-4">
        {tiles === null
          ? [0, 1, 2, 3].map((i) => <div key={i} className="h-[68px] animate-pulse rounded-xl bg-secondary/50" />)
          : tiles.map((t) => (
            <Link key={t.to} to={t.to} className="group flex items-center gap-3 rounded-xl border border-border/60 p-3 transition-colors hover:bg-secondary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <span className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-secondary', t.iconCls)}>{t.icon}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[11px] text-muted-foreground">{t.label}</p>
                <p className="truncate font-mono text-sm font-bold tabular-nums text-foreground">{t.value}</p>
                {t.sub && <p className="truncate text-[10px] text-muted-foreground">{t.sub}</p>}
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/40 transition-colors group-hover:text-foreground" />
            </Link>
          ))}
      </div>
    </Card>
  )
}

// ── trang chính ───────────────────────────────────────────
export default function TongQuanPage() {
  const [data, setData] = useState<MarketOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    marketApi
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

  return (
    <>
      <PageHeader
        title={VI.market.title}
        subtitle={VI.market.subtitle}
        actions={
          <div className="flex items-center gap-2">
            {updatedAt && (
              <span className="hidden text-xs text-muted-foreground sm:inline">{VI.market.updated} {updatedAt}</span>
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
        <Skeleton />
      ) : error && !data ? (
        <Card className="flex h-48 flex-col items-center justify-center gap-3 text-center">
          <BarChart3 className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{VI.market.empty}</p>
        </Card>
      ) : data ? (
        <div className="space-y-4">
          {/* Chỉ số */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {data.indices.map((idx) => <IndexCard key={idx.code} idx={idx} />)}
          </div>

          {/* Toàn cảnh các kênh đầu tư khác (vàng / xăng dầu / tiết kiệm / trái phiếu) */}
          <MultiAssetSummary />

          {/* Độ rộng */}
          <BreadthBar ov={data} />

          {/* Nhóm ngành */}
          {data.sectors.length > 0 && (
            <Card className="p-4">
              <div className="mb-3 flex items-center justify-between gap-2">
                <CardLabel icon={<Layers className="h-3.5 w-3.5" />}>{VI.market.sectors}</CardLabel>
                <span className="text-xs text-muted-foreground">Bình quân theo rổ {data.universeLabel}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
                {data.sectors.map((s) => <SectorTile key={s.name} s={s} />)}
              </div>
            </Card>
          )}

          {/* Top tăng / giảm */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <MoverCard title={VI.market.topGainers} icon={<TrendingUp className="h-3.5 w-3.5" />} movers={data.topGainers} empty={VI.common.noData} />
            <MoverCard title={VI.market.topLosers} icon={<TrendingDown className="h-3.5 w-3.5" />} movers={data.topLosers} empty={VI.common.noData} />
          </div>

          <p className="px-1 text-xs text-muted-foreground">Top tăng/giảm và độ rộng tính trong rổ {data.universeLabel}.</p>
        </div>
      ) : null}
    </>
  )
}
