import { useState, useEffect, useCallback } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table'
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  DollarSign,
  PieChart,
  Plus,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  AlertCircle,
  Loader2,
  Coins,
  PiggyBank,
  Landmark,
  Banknote,
  Trash2,
} from 'lucide-react'
import { PieChart as RPieChart, Pie, Cell, ResponsiveContainer, Tooltip as RTooltip, Legend } from 'recharts'
import { toast } from 'sonner'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardLabel } from '@/components/ui/card'
import { PriceChange } from '@/components/report/PriceChange'
import { cn } from '@/lib/utils'
import { fmtNum, fmtCompact, fmtPct, priceToneClass } from '@/utils/num'
import { VI } from '@/strings/vi'
import { portfolioApi } from '@/api/portfolio'
import type {
  PortfolioAccountItem,
  PortfolioAccountSnapshot,
  PortfolioPositionItem,
  PortfolioTradeListItem,
  OtherAssetItem,
  OtherAssetClass,
  OtherAssetListResponse,
} from '@/types/portfolio'

// ─── Hàng skeleton khi đang tải ──────────────────────────────────────────────

function LoadingRow({ cols }: { cols: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-3 py-3">
          <div className="h-4 animate-pulse rounded bg-secondary" />
        </td>
      ))}
    </tr>
  )
}

function SkeletonCard() {
  return (
    <Card className="p-5 space-y-2">
      <div className="h-3 w-24 animate-pulse rounded bg-secondary" />
      <div className="h-7 w-32 animate-pulse rounded bg-secondary" />
    </Card>
  )
}

// ─── Form tạo tài khoản mới ───────────────────────────────────────────────────

function CreateAccountForm({ onCreated }: { onCreated: (acc: PortfolioAccountItem) => void }) {
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const acc = await portfolioApi.createAccount({
        name: name.trim(),
        market: 'vn',
        baseCurrency: 'VND',
      })
      onCreated(acc)
      setName('')
    } catch {
      setError('Không thể tạo tài khoản. Vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 sm:flex-row sm:items-end"
      aria-label="Tạo tài khoản mới"
    >
      <div className="flex-1">
        <label htmlFor="acc-name" className="mb-1 block text-xs font-medium text-muted-foreground">
          Tên tài khoản
        </label>
        <input
          id="acc-name"
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Ví dụ: Tài khoản chứng khoán chính"
          className="h-9 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          required
          disabled={submitting}
        />
      </div>
      <button
        type="submit"
        disabled={submitting || !name.trim()}
        className="inline-flex h-9 min-w-[120px] items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Plus className="h-4 w-4" aria-hidden />}
        {VI.portfolio.addAccount}
      </button>
      {error && (
        <p className="text-xs text-danger flex items-center gap-1">
          <AlertCircle className="h-3.5 w-3.5" aria-hidden />
          {error}
        </p>
      )}
    </form>
  )
}

// ─── Form ghi giao dịch (mua/bán) — danh mục được dựng từ các giao dịch ───────

const tradeInputCls =
  'h-9 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50'

function CreateTradeForm({ accountId, onCreated }: { accountId: number; onCreated: () => void }) {
  const [symbol, setSymbol] = useState('')
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [tradeDate, setTradeDate] = useState(() => new Date().toLocaleDateString('en-CA'))
  const [quantity, setQuantity] = useState('')
  const [price, setPrice] = useState('')
  const [fee, setFee] = useState('')
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const sym = symbol.trim().toUpperCase()
    const q = parseFloat(quantity)
    const p = parseFloat(price)
    if (!sym || !(q > 0) || !(p > 0)) {
      setError('Vui lòng nhập mã, số lượng và giá hợp lệ.')
      return
    }
    const code = /^[A-Z]{2,3}$/.test(sym) ? `${sym}.VN` : sym
    setSubmitting(true)
    setError(null)
    try {
      await portfolioApi.createTrade({
        accountId,
        symbol: code,
        tradeDate,
        side,
        quantity: q,
        price: p,
        fee: parseFloat(fee) || 0,
        tax: 0,
        market: 'vn',
        currency: 'VND',
        note: note.trim() || undefined,
      })
      toast.success('Đã ghi giao dịch')
      setSymbol(''); setQuantity(''); setPrice(''); setFee(''); setNote('')
      onCreated()
    } catch {
      setError('Không thể ghi giao dịch. Hãy kiểm tra lại thông tin.')
    } finally {
      setSubmitting(false)
    }
  }

  const field = (label: string, node: React.ReactNode, span = 1) => (
    <div className={span === 2 ? 'col-span-2' : undefined}>
      <label className="mb-1 block text-xs font-medium text-muted-foreground">{label}</label>
      {node}
    </div>
  )

  return (
    <form onSubmit={handleSubmit} className="space-y-3" aria-label="Thêm giao dịch">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {field('Mã cổ phiếu', (
          <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} placeholder="VHM" className={cn(tradeInputCls, 'font-mono')} required disabled={submitting} />
        ))}
        {field('Loại lệnh', (
          <select value={side} onChange={e => setSide(e.target.value as 'buy' | 'sell')} className={cn(tradeInputCls, 'cursor-pointer')} disabled={submitting}>
            <option value="buy">Mua</option>
            <option value="sell">Bán</option>
          </select>
        ))}
        {field('Ngày giao dịch', (
          <input type="date" value={tradeDate} onChange={e => setTradeDate(e.target.value)} className={tradeInputCls} disabled={submitting} />
        ))}
        {field('Số lượng', (
          <input type="number" value={quantity} onChange={e => setQuantity(e.target.value)} placeholder="1000" className={cn(tradeInputCls, 'font-mono')} required disabled={submitting} min="0" step="any" />
        ))}
        {field('Giá (VND)', (
          <input type="number" value={price} onChange={e => setPrice(e.target.value)} placeholder="45000" className={cn(tradeInputCls, 'font-mono')} required disabled={submitting} min="0" step="any" />
        ))}
        {field('Phí + Thuế (VND)', (
          <input type="number" value={fee} onChange={e => setFee(e.target.value)} placeholder="0" className={cn(tradeInputCls, 'font-mono')} disabled={submitting} min="0" step="any" />
        ))}
        {field('Ghi chú', (
          <input value={note} onChange={e => setNote(e.target.value)} placeholder="(tuỳ chọn)" className={tradeInputCls} disabled={submitting} />
        ), 2)}
      </div>
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Plus className="h-4 w-4" aria-hidden />}
          Ghi giao dịch
        </button>
        {error && (
          <p className="flex items-center gap-1 text-xs text-danger">
            <AlertCircle className="h-3.5 w-3.5" aria-hidden />{error}
          </p>
        )}
      </div>
    </form>
  )
}

// ─── Thẻ tóm tắt snapshot ────────────────────────────────────────────────────

function SummaryCards({ snap }: { snap: PortfolioAccountSnapshot }) {
  const pnlClass = priceToneClass(snap.unrealizedPnl)
  const totalCost = snap.positions.reduce((s, p) => s + p.totalCost, 0)
  const pnlPct = totalCost > 0 ? (snap.unrealizedPnl / totalCost) * 100 : null

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Card className="p-4 space-y-1">
        <CardLabel icon={<Wallet className="h-3.5 w-3.5" aria-hidden />}>Giá trị thị trường</CardLabel>
        <p className="font-mono text-xl font-bold tabular-nums text-foreground">
          {fmtCompact(snap.totalMarketValue)}
        </p>
        <p className="text-xs text-muted-foreground">VND</p>
      </Card>

      <Card className="p-4 space-y-1">
        <CardLabel icon={<DollarSign className="h-3.5 w-3.5" aria-hidden />}>Tổng vốn đầu tư</CardLabel>
        <p className="font-mono text-xl font-bold tabular-nums text-foreground">
          {fmtCompact(totalCost)}
        </p>
        <p className="text-xs text-muted-foreground">VND</p>
      </Card>

      <Card className="p-4 space-y-1">
        <CardLabel
          icon={
            snap.unrealizedPnl >= 0
              ? <TrendingUp className="h-3.5 w-3.5" aria-hidden />
              : <TrendingDown className="h-3.5 w-3.5" aria-hidden />
          }
        >
          Lãi/Lỗ chưa thực hiện
        </CardLabel>
        <p className={cn('font-mono text-xl font-bold tabular-nums', pnlClass)}>
          {snap.unrealizedPnl >= 0 ? '+' : ''}{fmtCompact(snap.unrealizedPnl)}
        </p>
        {pnlPct !== null && (
          <p className={cn('text-xs font-medium tabular-nums', pnlClass)}>
            {fmtPct(pnlPct)}
          </p>
        )}
      </Card>

      <Card className="p-4 space-y-1">
        <CardLabel icon={<PieChart className="h-3.5 w-3.5" aria-hidden />}>Tổng tài sản ròng</CardLabel>
        <p className="font-mono text-xl font-bold tabular-nums text-foreground">
          {fmtCompact(snap.totalEquity)}
        </p>
        <p className="text-xs text-muted-foreground">
          Tiền mặt: {fmtCompact(snap.totalCash)}
        </p>
      </Card>
    </div>
  )
}

// ─── Bảng cổ phiếu nắm giữ (TanStack) ────────────────────────────────────────

const colHelper = createColumnHelper<PortfolioPositionItem>()

function HoldingsTable({
  positions,
  totalMarketValue,
}: {
  positions: PortfolioPositionItem[]
  totalMarketValue: number
}) {
  const [sorting, setSorting] = useState<SortingState>([])

  const columns = [
    colHelper.accessor('symbol', {
      header: VI.portfolio.symbol,
      cell: info => (
        <span className="font-mono font-bold tracking-wide text-foreground">
          {info.getValue()}
        </span>
      ),
    }),
    colHelper.accessor('quantity', {
      header: VI.portfolio.quantity,
      cell: info => (
        <span className="font-mono tabular-nums">{fmtNum(info.getValue(), 0)}</span>
      ),
    }),
    colHelper.accessor('avgCost', {
      header: VI.portfolio.avgPrice,
      cell: info => <span className="font-mono tabular-nums">{fmtNum(info.getValue())}</span>,
    }),
    colHelper.accessor('lastPrice', {
      header: VI.portfolio.marketPrice,
      cell: info => (
        <PriceChange price={info.getValue()} size="sm" />
      ),
    }),
    colHelper.accessor('marketValueBase', {
      header: VI.portfolio.marketValue,
      cell: info => (
        <span className="font-mono tabular-nums">{fmtCompact(info.getValue())}</span>
      ),
    }),
    colHelper.accessor('unrealizedPnlBase', {
      header: VI.portfolio.pnl,
      cell: info => {
        const pnl = info.getValue()
        const pct = info.row.original.unrealizedPnlPct
        return (
          <span className={cn('font-mono tabular-nums', priceToneClass(pnl))}>
            {pnl >= 0 ? '+' : ''}{fmtCompact(pnl)}
            {pct != null && (
              <span className="ml-1 text-xs">({fmtPct(pct)})</span>
            )}
          </span>
        )
      },
    }),
    colHelper.display({
      id: 'weight',
      header: VI.portfolio.weight,
      cell: info => {
        const w = totalMarketValue > 0
          ? (info.row.original.marketValueBase / totalMarketValue) * 100
          : 0
        return (
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-16 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.min(w, 100)}%` }}
              />
            </div>
            <span className="font-mono tabular-nums text-xs">{fmtPct(w)}</span>
          </div>
        )
      },
    }),
  ]

  const table = useReactTable({
    data: positions,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  if (positions.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-muted-foreground">{VI.common.noData}</p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          {table.getHeaderGroups().map(hg => (
            <tr key={hg.id} className="border-b border-border">
              {hg.headers.map(header => (
                <th
                  key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  className={cn(
                    'px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground',
                    header.column.getCanSort() && 'cursor-pointer select-none hover:text-foreground',
                  )}
                >
                  <span className="inline-flex items-center gap-1">
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    {header.column.getCanSort() && (
                      header.column.getIsSorted() === 'asc' ? (
                        <ArrowUp className="h-3 w-3" aria-hidden />
                      ) : header.column.getIsSorted() === 'desc' ? (
                        <ArrowDown className="h-3 w-3" aria-hidden />
                      ) : (
                        <ArrowUpDown className="h-3 w-3 opacity-40" aria-hidden />
                      )
                    )}
                  </span>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => (
            <tr
              key={row.id}
              className="border-b border-border/50 transition-colors hover:bg-secondary/40"
            >
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} className="px-3 py-3">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Giao dịch gần đây ────────────────────────────────────────────────────────

function TradesSection({ accountId, refreshTick = 0 }: { accountId: number; refreshTick?: number }) {
  const [trades, setTrades] = useState<PortfolioTradeListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 8
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchTrades = useCallback(async (p: number) => {
    setLoading(true)
    setError(null)
    try {
      const res = await portfolioApi.listTrades({ accountId, page: p, pageSize })
      setTrades(res.items)
      setTotal(res.total)
    } catch {
      setError(VI.errors.generic)
    } finally {
      setLoading(false)
    }
  }, [accountId])

  useEffect(() => {
    setPage(1)
    fetchTrades(1)
  }, [fetchTrades, refreshTick])

  const totalPages = Math.ceil(total / pageSize)

  const handlePage = (p: number) => {
    setPage(p)
    fetchTrades(p)
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="font-heading font-semibold text-foreground">Giao dịch gần đây</h2>
        <button
          type="button"
          onClick={() => handlePage(page)}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={VI.common.refresh}
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-5 py-4 text-sm text-danger">
          <AlertCircle className="h-4 w-4" aria-hidden />
          {error}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              {['Ngày', 'Mã', 'Loại', 'Số lượng', 'Giá', 'Phí + Thuế', 'Ghi chú'].map(col => (
                <th
                  key={col}
                  className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 4 }).map((_, i) => <LoadingRow key={i} cols={7} />)
              : trades.length === 0
                ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                      {VI.common.noData}
                    </td>
                  </tr>
                )
                : trades.map(t => (
                  <tr
                    key={t.id}
                    className="border-b border-border/50 transition-colors hover:bg-secondary/40"
                  >
                    <td className="px-4 py-3 font-mono text-xs tabular-nums text-muted-foreground">
                      {t.tradeDate}
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono font-bold tracking-wide text-foreground">{t.symbol}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold',
                          t.side === 'buy'
                            ? 'bg-up/10 text-up'
                            : 'bg-down/10 text-down',
                        )}
                      >
                        {t.side === 'buy' ? 'Mua' : 'Bán'}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums">
                      {fmtNum(t.quantity, 0)}
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums">
                      {fmtNum(t.price)}
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums text-muted-foreground">
                      {fmtNum(t.fee + t.tax)}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground max-w-[120px] truncate">
                      {t.note ?? '—'}
                    </td>
                  </tr>
                ))
            }
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          <p className="text-xs text-muted-foreground">
            {VI.common.total}: <span className="font-semibold">{fmtNum(total, 0)}</span> giao dịch
          </p>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => handlePage(page - 1)}
              disabled={page <= 1 || loading}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-secondary disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={VI.common.prev}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden />
            </button>
            <span className="px-2 text-xs text-muted-foreground">
              {VI.common.page} {page}/{totalPages}
            </span>
            <button
              type="button"
              onClick={() => handlePage(page + 1)}
              disabled={page >= totalPages || loading}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-secondary disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={VI.common.next}
            >
              <ChevronRight className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      )}
    </Card>
  )
}

// ─── Tài sản khác (vàng / tiết kiệm / trái phiếu) + phân bổ tài sản ───────────

const cssVar = (name: string, fallback: string) =>
  typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    : fallback

// Màu cho từng lớp tài sản trong biểu đồ phân bổ.
const CLASS_COLOR: Record<string, string> = {
  co_phieu: cssVar('--primary', '#3b82f6'),
  tien_mat: cssVar('--neutral-slate', '#94a3b8'),
  vang: '#f59e0b',
  tiet_kiem: '#10b981',
  trai_phieu: '#8b5cf6',
}

const CLASS_ICON: Record<OtherAssetClass, typeof Coins> = {
  vang: Coins,
  tiet_kiem: PiggyBank,
  trai_phieu: Landmark,
}

const otherInputCls =
  'h-9 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50'

/** Biểu đồ tròn cơ cấu toàn bộ tài sản: cổ phiếu + tiền mặt + vàng/tiết kiệm/trái phiếu. */
function AssetAllocationCard({
  snapshot,
  otherByClass,
}: {
  snapshot: PortfolioAccountSnapshot
  otherByClass: { assetClass: OtherAssetClass; label: string; value: number }[]
}) {
  const rows = [
    { key: 'co_phieu', label: VI.portfolio.classCoPhieu, value: snapshot.totalMarketValue },
    { key: 'tien_mat', label: VI.portfolio.classTienMat, value: snapshot.totalCash },
    ...otherByClass.map(o => ({ key: o.assetClass, label: o.label, value: o.value })),
  ].filter(r => r.value > 0)

  const total = rows.reduce((s, r) => s + r.value, 0)
  if (total <= 0) {
    return (
      <Card className="p-5">
        <CardLabel icon={<PieChart className="h-3.5 w-3.5" aria-hidden />}>{VI.portfolio.allocationTitle}</CardLabel>
        <p className="py-8 text-center text-sm text-muted-foreground">{VI.common.noData}</p>
      </Card>
    )
  }

  return (
    <Card className="p-5">
      <CardLabel icon={<PieChart className="h-3.5 w-3.5" aria-hidden />}>{VI.portfolio.allocationTitle}</CardLabel>
      <p className="mb-2 mt-1 text-xs text-muted-foreground">{VI.portfolio.allocationHint}</p>
      <div className="grid items-center gap-4 sm:grid-cols-2">
        <ResponsiveContainer width="100%" height={220}>
          <RPieChart>
            <Pie data={rows} dataKey="value" nameKey="label" cx="50%" cy="50%" innerRadius={52} outerRadius={88} paddingAngle={2}>
              {rows.map(r => (
                <Cell key={r.key} fill={CLASS_COLOR[r.key] ?? '#64748b'} stroke={cssVar('--card', '#0f172a')} strokeWidth={2} />
              ))}
            </Pie>
            <RTooltip
              contentStyle={{ background: cssVar('--card', '#0f172a'), border: `1px solid ${cssVar('--border', '#334155')}`, borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: cssVar('--foreground', '#f8fafc') }}
              formatter={(value) => fmtCompact(Number(value))}
            />
            <Legend formatter={(v) => <span className="text-xs text-muted-foreground">{v}</span>} />
          </RPieChart>
        </ResponsiveContainer>
        <div className="space-y-1.5">
          <div className="mb-2 flex items-center justify-between border-b border-border/50 pb-2">
            <span className="text-xs font-medium text-muted-foreground">{VI.portfolio.totalNetWorth}</span>
            <span className="font-mono text-base font-bold tabular-nums text-foreground">{fmtCompact(total)}</span>
          </div>
          {rows.map(r => (
            <div key={r.key} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-sm text-foreground">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: CLASS_COLOR[r.key] ?? '#64748b' }} aria-hidden />
                {r.label}
              </span>
              <span className="font-mono text-xs tabular-nums text-muted-foreground">
                {fmtCompact(r.value)} · {fmtPct((r.value / total) * 100)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

/** Khu vực tài sản khác: form thêm + bảng danh sách + xoá. */
function OtherAssetsSection({
  accountId,
  assets,
  onChange,
}: {
  accountId: number
  assets: OtherAssetItem[]
  onChange: () => void
}) {
  const [showForm, setShowForm] = useState(false)
  const [assetClass, setAssetClass] = useState<OtherAssetClass>('vang')
  const [label, setLabel] = useState('')
  const [value, setValue] = useState('')
  const [rate, setRate] = useState('')
  const [maturity, setMaturity] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const needsRate = assetClass === 'tiet_kiem' || assetClass === 'trai_phieu'

  const reset = () => { setLabel(''); setValue(''); setRate(''); setMaturity(''); setError(null) }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const v = parseFloat(value)
    if (!label.trim() || !(v >= 0)) {
      setError('Vui lòng nhập tên và giá trị hợp lệ.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await portfolioApi.createOtherAsset({
        accountId,
        assetClass,
        label: label.trim(),
        value: v,
        interestRate: needsRate && rate ? parseFloat(rate) : undefined,
        maturityDate: needsRate && maturity ? maturity : undefined,
      })
      toast.success(VI.portfolio.assetAdded)
      reset()
      setShowForm(false)
      onChange()
    } catch {
      setError('Không thể thêm tài sản. Hãy thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await portfolioApi.deleteOtherAsset(id)
      toast.success(VI.portfolio.assetDeleted)
      onChange()
    } catch {
      toast.error('Không thể xoá tài sản.')
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-border px-5 py-4">
        <div>
          <h2 className="font-heading font-semibold text-foreground">{VI.portfolio.otherAssets}</h2>
          <p className="text-xs text-muted-foreground">{VI.portfolio.otherAssetsHint}</p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm(v => !v)}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm font-medium text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden />{VI.portfolio.addOtherAsset}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="space-y-3 border-b border-border bg-background/40 px-5 py-4" aria-label={VI.portfolio.addOtherAsset}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">{VI.portfolio.assetClass}</label>
              <select value={assetClass} onChange={e => setAssetClass(e.target.value as OtherAssetClass)} className={cn(otherInputCls, 'cursor-pointer')} disabled={submitting}>
                <option value="vang">{VI.portfolio.classVang}</option>
                <option value="tiet_kiem">{VI.portfolio.classTietKiem}</option>
                <option value="trai_phieu">{VI.portfolio.classTraiPhieu}</option>
              </select>
            </div>
            <div className={needsRate ? '' : 'col-span-2'}>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">{VI.portfolio.assetLabel}</label>
              <input value={label} onChange={e => setLabel(e.target.value)} placeholder="Vàng SJC / Sổ TK VCB…" className={otherInputCls} required disabled={submitting} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">{VI.portfolio.assetValue}</label>
              <input type="number" value={value} onChange={e => setValue(e.target.value)} placeholder="100000000" className={cn(otherInputCls, 'font-mono')} required disabled={submitting} min="0" step="any" />
            </div>
            {needsRate && (
              <>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">{VI.portfolio.interestRate}</label>
                  <input type="number" value={rate} onChange={e => setRate(e.target.value)} placeholder="5.1" className={cn(otherInputCls, 'font-mono')} disabled={submitting} min="0" step="any" />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">{VI.portfolio.maturityDate}</label>
                  <input type="date" value={maturity} onChange={e => setMaturity(e.target.value)} className={otherInputCls} disabled={submitting} />
                </div>
              </>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button type="submit" disabled={submitting} className="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Plus className="h-4 w-4" aria-hidden />}
              {VI.portfolio.addOtherAsset}
            </button>
            {error && <p className="flex items-center gap-1 text-xs text-danger"><AlertCircle className="h-3.5 w-3.5" aria-hidden />{error}</p>}
          </div>
        </form>
      )}

      {assets.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-muted-foreground">{VI.portfolio.noOtherAssets}</p>
      ) : (
        <ul className="divide-y divide-border/50">
          {assets.map(a => {
            const Icon = CLASS_ICON[a.assetClass] ?? Banknote
            return (
              <li key={a.id} className="flex items-center gap-3 px-5 py-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" style={{ background: (CLASS_COLOR[a.assetClass] ?? '#64748b') + '22', color: CLASS_COLOR[a.assetClass] ?? '#64748b' }}>
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-foreground">{a.label}</p>
                  <p className="text-xs text-muted-foreground">
                    {a.assetClassLabel}
                    {a.interestRate != null && <> · {a.interestRate}%/năm</>}
                    {a.maturityDate && <> · đáo hạn {a.maturityDate}</>}
                  </p>
                </div>
                <span className="font-mono text-sm font-semibold tabular-nums text-foreground">{fmtCompact(a.value)}</span>
                <button
                  type="button"
                  onClick={() => handleDelete(a.id)}
                  aria-label={VI.portfolio.deleteAsset}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-danger/10 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden />
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

// ─── Trang chính ─────────────────────────────────────────────────────────────

export default function DanhMucPage() {
  const [accounts, setAccounts] = useState<PortfolioAccountItem[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [accountsLoading, setAccountsLoading] = useState(true)
  const [accountsError, setAccountsError] = useState<string | null>(null)

  const [snapshot, setSnapshot] = useState<PortfolioAccountSnapshot | null>(null)
  const [snapLoading, setSnapLoading] = useState(false)
  const [snapError, setSnapError] = useState<string | null>(null)

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showTradeForm, setShowTradeForm] = useState(false)
  const [tradesRefresh, setTradesRefresh] = useState(0)

  const [otherAssets, setOtherAssets] = useState<OtherAssetListResponse | null>(null)

  // Tải danh sách tài khoản
  const loadAccounts = useCallback(async () => {
    setAccountsLoading(true)
    setAccountsError(null)
    try {
      const res = await portfolioApi.getAccounts()
      setAccounts(res.accounts)
      if (res.accounts.length > 0 && selectedId === null) {
        setSelectedId(res.accounts[0].id)
      }
    } catch {
      setAccountsError(VI.errors.generic)
    } finally {
      setAccountsLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    loadAccounts()
  }, [loadAccounts])

  // Tải snapshot khi chọn tài khoản
  const loadSnapshot = useCallback(() => {
    if (selectedId === null) {
      setSnapshot(null)
      return
    }
    setSnapLoading(true)
    setSnapError(null)
    portfolioApi
      .getSnapshot({ accountId: selectedId })
      .then(res => {
        const acc = res.accounts.find(a => a.accountId === selectedId) ?? res.accounts[0] ?? null
        setSnapshot(acc)
      })
      .catch(() => setSnapError(VI.errors.generic))
      .finally(() => setSnapLoading(false))
  }, [selectedId])

  useEffect(() => {
    loadSnapshot()
  }, [loadSnapshot])

  // Tải tài sản khác (vàng / tiết kiệm / trái phiếu) theo tài khoản
  const loadOtherAssets = useCallback(() => {
    if (selectedId === null) {
      setOtherAssets(null)
      return
    }
    portfolioApi
      .listOtherAssets(selectedId)
      .then(setOtherAssets)
      .catch(() => setOtherAssets(null))
  }, [selectedId])

  useEffect(() => {
    loadOtherAssets()
  }, [loadOtherAssets])

  const handleAccountCreated = (acc: PortfolioAccountItem) => {
    setAccounts(prev => [...prev, acc])
    setSelectedId(acc.id)
    setShowCreateForm(false)
  }

  // Sau khi ghi giao dịch: nạp lại danh mục + lịch sử giao dịch
  const handleTradeCreated = () => {
    loadSnapshot()
    setTradesRefresh(t => t + 1)
  }

  const selectedAccount = accounts.find(a => a.id === selectedId)

  return (
    <>
      <PageHeader
        title={VI.portfolio.title}
        subtitle="Theo dõi danh mục và lịch sử giao dịch"
        actions={
          <button
            type="button"
            onClick={() => setShowCreateForm(v => !v)}
            className="inline-flex h-9 min-w-[44px] items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={VI.portfolio.addAccount}
          >
            <Plus className="h-4 w-4" aria-hidden />
            {VI.portfolio.addAccount}
          </button>
        }
      />

      {/* Form tạo tài khoản */}
      {showCreateForm && (
        <Card className="mb-5 p-5">
          <h2 className="mb-4 font-heading font-semibold text-foreground">Tạo tài khoản mới</h2>
          <CreateAccountForm onCreated={handleAccountCreated} />
        </Card>
      )}

      {/* Lỗi tải tài khoản */}
      {accountsError && (
        <div className="mb-5 flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-3 text-sm text-danger">
          <AlertCircle className="h-4 w-4" aria-hidden />
          {accountsError}
          <button
            type="button"
            onClick={loadAccounts}
            className="ml-auto text-xs underline hover:no-underline"
          >
            {VI.common.retry}
          </button>
        </div>
      )}

      {/* Đang tải tài khoản */}
      {accountsLoading && (
        <div className="mb-5 flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          {VI.common.loading}
        </div>
      )}

      {/* Trạng thái rỗng — chưa có tài khoản */}
      {!accountsLoading && !accountsError && accounts.length === 0 && (
        <div className="flex min-h-[320px] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 p-10 text-center">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Wallet className="h-6 w-6" aria-hidden />
          </span>
          <p className="mb-4 text-sm text-muted-foreground">{VI.portfolio.emptyState}</p>
          <button
            type="button"
            onClick={() => setShowCreateForm(true)}
            className="inline-flex h-10 min-w-[44px] items-center gap-2 rounded-lg bg-primary px-5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Plus className="h-4 w-4" aria-hidden />
            {VI.portfolio.addAccount}
          </button>
        </div>
      )}

      {/* Giao diện chính khi có tài khoản */}
      {!accountsLoading && accounts.length > 0 && (
        <div className="space-y-6">
          {/* Bộ chọn tài khoản */}
          <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label={VI.portfolio.account}>
            {accounts.map(acc => (
              <button
                key={acc.id}
                type="button"
                role="tab"
                aria-selected={acc.id === selectedId}
                onClick={() => setSelectedId(acc.id)}
                className={cn(
                  'inline-flex h-9 min-w-[44px] items-center rounded-lg border px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  acc.id === selectedId
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border bg-card text-foreground hover:bg-secondary',
                )}
              >
                {acc.name}
              </button>
            ))}
          </div>

          {/* Thông tin tài khoản đang chọn */}
          {selectedAccount && (
            <p className="text-sm text-muted-foreground">
              Tài khoản: <span className="font-semibold text-foreground">{selectedAccount.name}</span>
              {selectedAccount.broker && (
                <> · Môi giới: <span className="font-semibold">{selectedAccount.broker}</span></>
              )}
              <> · Thị trường: <span className="font-mono uppercase">{selectedAccount.market}</span></>
            </p>
          )}

          {/* Skeleton snapshot */}
          {snapLoading && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          )}

          {snapError && (
            <div className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-3 text-sm text-danger">
              <AlertCircle className="h-4 w-4" aria-hidden />
              {snapError}
            </div>
          )}

          {!snapLoading && snapshot && (
            <>
              <SummaryCards snap={snapshot} />

              {/* Phân bổ tài sản (cổ phiếu + tiền mặt + vàng/tiết kiệm/trái phiếu) */}
              <AssetAllocationCard snapshot={snapshot} otherByClass={otherAssets?.byClass ?? []} />

              {/* Bảng cổ phiếu nắm giữ */}
              <Card className="overflow-hidden">
                <div className="flex items-center justify-between gap-2 border-b border-border px-5 py-4">
                  <h2 className="font-heading font-semibold text-foreground">
                    {VI.portfolio.holdings}
                    {snapshot.positions.length > 0 && (
                      <span className="ml-2 rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-muted-foreground">
                        {snapshot.positions.length} mã
                      </span>
                    )}
                  </h2>
                  {selectedId !== null && (
                    <button
                      type="button"
                      onClick={() => setShowTradeForm(v => !v)}
                      className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm font-medium text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Plus className="h-3.5 w-3.5" aria-hidden />
                      Thêm giao dịch
                    </button>
                  )}
                </div>
                {showTradeForm && selectedId !== null && (
                  <div className="border-b border-border bg-background/40 px-5 py-4">
                    <CreateTradeForm accountId={selectedId} onCreated={handleTradeCreated} />
                  </div>
                )}
                <HoldingsTable
                  positions={snapshot.positions}
                  totalMarketValue={snapshot.totalMarketValue}
                />
              </Card>

              {/* Tài sản khác: vàng / tiết kiệm / trái phiếu */}
              {selectedId !== null && (
                <OtherAssetsSection
                  accountId={selectedId}
                  assets={otherAssets?.items ?? []}
                  onChange={loadOtherAssets}
                />
              )}

              {/* Giao dịch gần đây */}
              {selectedId !== null && <TradesSection accountId={selectedId} refreshTick={tradesRefresh} />}
            </>
          )}

          {!snapLoading && !snapError && !snapshot && selectedId !== null && (
            <p className="py-8 text-center text-sm text-muted-foreground">{VI.common.noData}</p>
          )}
        </div>
      )}
    </>
  )
}
