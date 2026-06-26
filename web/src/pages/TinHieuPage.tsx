import { useState, useCallback, useEffect, useRef } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
  flexRender,
} from '@tanstack/react-table'
import {
  AlertTriangle,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  X,
  TrendingUp,
  Eye,
  ShieldAlert,
  Zap,
  AlertCircle,
  CalendarDays,
  Target,
  ArrowRightLeft,
  Loader2,
  Radar,
} from 'lucide-react'
import { toast } from 'sonner'
import { decisionSignalsApi } from '@/api/decisionSignals'
import type {
  DecisionSignalItem,
  DecisionSignalListParams,
  DecisionSignalListResponse,
  DecisionSignalStatus,
} from '@/types/decisionSignals'
import type { DecisionAction } from '@/types/analysis'
import { Card } from '@/components/ui/card'
import { PageHeader } from '@/components/common/PageHeader'
import { fmtPrice, fmtNum } from '@/utils/num'
import { cn } from '@/lib/utils'
import { VI } from '@/strings/vi'

// ─── Simple fetch hook (no react-query; not in package.json) ─────────────────

type FetchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: DecisionSignalListResponse }
  | { status: 'error'; message: string }

function useSignals(params: DecisionSignalListParams, reloadKey = 0): FetchState {
  const [state, setState] = useState<FetchState>({ status: 'loading' })
  const paramsKey = JSON.stringify(params)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setState({ status: 'loading' })
    decisionSignalsApi.list(params)
      .then((data) => {
        if (!ctrl.signal.aborted) setState({ status: 'success', data })
      })
      .catch((err: unknown) => {
        if (!ctrl.signal.aborted) {
          const msg = err instanceof Error ? err.message : 'Đã xảy ra lỗi khi tải tín hiệu.'
          setState({ status: 'error', message: msg })
        }
      })
    return () => ctrl.abort()
    // paramsKey stringifies the whole params object so we can dep on it safely
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey, reloadKey])

  return state
}

// ─── Mapping helpers ────────────────────────────────────────────────────────

function actionLabel(action: DecisionAction): string {
  const map: Record<string, string> = {
    buy: 'Mua',
    add: 'Mua thêm',
    sell: 'Bán',
    reduce: 'Giảm vị thế',
    avoid: 'Tránh',
    hold: 'Giữ',
    watch: 'Theo dõi',
  }
  return map[action] ?? action
}

function actionToneClass(action: DecisionAction): string {
  if (action === 'buy' || action === 'add') return 'bg-up/15 text-up'
  if (action === 'sell' || action === 'reduce' || action === 'avoid') return 'bg-down/15 text-down'
  return 'bg-warning/15 text-warning'
}

function statusLabel(status: DecisionSignalItem['status']): string {
  const map: Record<string, string> = {
    active: 'Hoạt động',
    expired: 'Hết hạn',
    invalidated: 'Vô hiệu',
    closed: 'Đã đóng',
    archived: 'Lưu trữ',
  }
  return map[status] ?? status
}

function statusBadgeClass(status: DecisionSignalItem['status']): string {
  if (status === 'active') return 'bg-up/10 text-up'
  if (status === 'invalidated') return 'bg-down/10 text-down'
  return 'bg-secondary text-secondary-foreground'
}

function horizonLabel(horizon: DecisionSignalItem['horizon']): string {
  if (!horizon) return '--'
  const map: Record<string, string> = {
    intraday: 'Ngày',
    '1d': '1 ngày',
    '3d': '3 ngày',
    '5d': '5 ngày',
    '10d': '10 ngày',
    swing: 'Ngắn hạn',
    long: 'Dài hạn',
  }
  return map[horizon] ?? horizon
}

function formatDateShort(iso?: string | null): string {
  if (!iso) return '--'
  try {
    return new Date(iso).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: '2-digit' })
  } catch {
    return '--'
  }
}

function formatDateFull(iso?: string | null): string {
  if (!iso) return '--'
  try {
    return new Date(iso).toLocaleString('vi-VN')
  } catch {
    return '--'
  }
}

// ─── Detail Section helper ────────────────────────────────────────────────────

function DetailSection({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="rounded-xl border border-border bg-background/40 p-3">
      <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}
        {label}
      </p>
      <div className="text-sm leading-6 text-foreground">{children}</div>
    </div>
  )
}

// ─── Detail Drawer ────────────────────────────────────────────────────────────

function SignalDetailDrawer({
  signal,
  onClose,
}: {
  signal: DecisionSignalItem
  onClose: () => void
}) {
  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <aside
        role="dialog"
        aria-label={`Chi tiết tín hiệu ${signal.stockCode}`}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col overflow-y-auto bg-card shadow-2xl"
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-card px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="font-heading text-lg font-bold text-foreground">
                {signal.stockName || signal.stockCode}
              </h2>
              <span className="rounded-md bg-secondary px-2 py-0.5 font-mono text-xs text-secondary-foreground">
                {signal.stockCode}
              </span>
            </div>
            <span
              className={cn(
                'mt-1 inline-block rounded-md px-2 py-0.5 text-xs font-semibold',
                actionToneClass(signal.action),
              )}
            >
              {signal.actionLabel || actionLabel(signal.action)}
            </span>
          </div>
          <button
            type="button"
            aria-label="Đóng chi tiết"
            onClick={onClose}
            className="ml-4 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 space-y-3 p-5">
          {/* Chỉ số chính */}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="rounded-xl border border-border bg-background/40 p-3">
              <p className="text-[11px] font-medium text-muted-foreground">Độ tin cậy</p>
              <p className="mt-0.5 font-mono text-base font-semibold tabular-nums text-foreground">
                {signal.confidence != null ? `${fmtNum(signal.confidence * 100, 0)}%` : '--'}
              </p>
            </div>
            <div className="rounded-xl border border-border bg-background/40 p-3">
              <p className="text-[11px] font-medium text-muted-foreground">Điểm AI</p>
              <p className="mt-0.5 font-mono text-base font-semibold tabular-nums text-foreground">
                {signal.score != null ? fmtNum(signal.score, 1) : '--'}
              </p>
            </div>
            <div className="rounded-xl border border-border bg-background/40 p-3">
              <p className="text-[11px] font-medium text-muted-foreground">Khung thời gian</p>
              <p className="mt-0.5 text-base font-semibold text-foreground">{horizonLabel(signal.horizon)}</p>
            </div>
            <div className="rounded-xl border border-border bg-background/40 p-3">
              <p className="text-[11px] font-medium text-muted-foreground">Trạng thái</p>
              <span
                className={cn(
                  'mt-0.5 inline-block rounded-md px-2 py-0.5 text-xs font-semibold',
                  statusBadgeClass(signal.status),
                )}
              >
                {statusLabel(signal.status)}
              </span>
            </div>
          </div>

          {/* Giá */}
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-xl border border-border bg-background/40 p-3">
              <p className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
                <ArrowRightLeft className="h-3 w-3" />
                Vùng mua
              </p>
              <p className="mt-0.5 font-mono text-sm font-semibold tabular-nums text-foreground">
                {signal.entryLow != null && signal.entryHigh != null
                  ? `${fmtPrice(signal.entryLow)} – ${fmtPrice(signal.entryHigh)}`
                  : signal.entryLow != null
                  ? fmtPrice(signal.entryLow)
                  : signal.entryHigh != null
                  ? fmtPrice(signal.entryHigh)
                  : '--'}
              </p>
            </div>
            <div className="rounded-xl border border-border bg-background/40 p-3">
              <p className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
                <ShieldAlert className="h-3 w-3" />
                Cắt lỗ
              </p>
              <p className="mt-0.5 font-mono text-sm font-semibold tabular-nums text-down">
                {signal.stopLoss != null ? fmtPrice(signal.stopLoss) : '--'}
              </p>
            </div>
            <div className="rounded-xl border border-border bg-background/40 p-3">
              <p className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
                <Target className="h-3 w-3" />
                Mục tiêu
              </p>
              <p className="mt-0.5 font-mono text-sm font-semibold tabular-nums text-up">
                {signal.targetPrice != null ? fmtPrice(signal.targetPrice) : '--'}
              </p>
            </div>
          </div>

          {/* Lý do */}
          {signal.reason && typeof signal.reason === 'string' && (
            <DetailSection icon={<Eye className="h-3.5 w-3.5" />} label="Lý do tín hiệu">
              {signal.reason}
            </DetailSection>
          )}

          {/* Rủi ro */}
          {signal.riskSummary && typeof signal.riskSummary === 'string' && (
            <DetailSection icon={<ShieldAlert className="h-3.5 w-3.5" />} label="Tóm tắt rủi ro">
              {signal.riskSummary}
            </DetailSection>
          )}

          {/* Xúc tác */}
          {signal.catalystSummary && typeof signal.catalystSummary === 'string' && (
            <DetailSection icon={<Zap className="h-3.5 w-3.5" />} label="Chất xúc tác">
              {signal.catalystSummary}
            </DetailSection>
          )}

          {/* Điều kiện theo dõi */}
          {signal.watchConditions && typeof signal.watchConditions === 'string' && (
            <DetailSection icon={<Eye className="h-3.5 w-3.5" />} label="Điều kiện theo dõi">
              {signal.watchConditions}
            </DetailSection>
          )}

          {/* Vô hiệu hóa */}
          {signal.invalidation && typeof signal.invalidation === 'string' && (
            <DetailSection icon={<AlertCircle className="h-3.5 w-3.5" />} label="Điều kiện vô hiệu">
              {signal.invalidation}
            </DetailSection>
          )}

          {/* Thời gian */}
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-border bg-background/40 p-3">
              <p className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
                <CalendarDays className="h-3 w-3" />
                Ngày tạo
              </p>
              <p className="mt-0.5 text-sm text-foreground">{formatDateFull(signal.createdAt)}</p>
            </div>
            {signal.expiresAt && (
              <div className="rounded-xl border border-border bg-background/40 p-3">
                <p className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
                  <CalendarDays className="h-3 w-3" />
                  Hết hạn
                </p>
                <p className="mt-0.5 text-sm text-foreground">{formatDateFull(signal.expiresAt)}</p>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  )
}

// ─── Loading Skeleton ─────────────────────────────────────────────────────────

function TableSkeleton() {
  return (
    <div className="space-y-2 p-4" aria-busy aria-label="Đang tải danh sách tín hiệu">
      {Array.from({ length: 7 }).map((_, i) => (
        <div
          key={i}
          className="h-12 animate-pulse rounded-lg bg-secondary/50"
          style={{ opacity: 1 - i * 0.1 }}
        />
      ))}
    </div>
  )
}

// ─── Confidence Bar ───────────────────────────────────────────────────────────

function ConfidenceBar({ value }: { value?: number | null }) {
  if (value == null) return <span className="text-muted-foreground">--</span>
  const pct = Math.round(value * 100)
  const barColor = pct >= 70 ? 'bg-up' : pct >= 40 ? 'bg-warning' : 'bg-down'
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-secondary">
        <div className={cn('h-full rounded-full', barColor)} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs tabular-nums text-foreground">{pct}%</span>
    </div>
  )
}

// ─── Filter select styles ────────────────────────────────────────────────────

const selectClass =
  'h-9 rounded-lg border border-border bg-card px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

// ─── Constants ───────────────────────────────────────────────────────────────

const ACTION_OPTIONS: { value: DecisionAction | ''; label: string }[] = [
  { value: '', label: 'Tất cả hành động' },
  { value: 'buy', label: 'Mua' },
  { value: 'add', label: 'Mua thêm' },
  { value: 'hold', label: 'Giữ' },
  { value: 'watch', label: 'Theo dõi' },
  { value: 'sell', label: 'Bán' },
  { value: 'reduce', label: 'Giảm vị thế' },
  { value: 'avoid', label: 'Tránh' },
]

const STATUS_OPTIONS: { value: DecisionSignalStatus | ''; label: string }[] = [
  { value: '', label: 'Tất cả trạng thái' },
  { value: 'active', label: 'Hoạt động' },
  { value: 'expired', label: 'Hết hạn' },
  { value: 'invalidated', label: 'Vô hiệu' },
  { value: 'closed', label: 'Đã đóng' },
  { value: 'archived', label: 'Lưu trữ' },
]

const PAGE_SIZE = 20

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function TinHieuPage() {
  const [filterAction, setFilterAction] = useState<DecisionAction | ''>('')
  const [filterStatus, setFilterStatus] = useState<DecisionSignalStatus | ''>('')
  const [scope, setScope] = useState<'all' | 'holding'>('all')
  const [scanning, setScanning] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [page, setPage] = useState(1)
  const [sorting, setSorting] = useState<SortingState>([])
  const [selectedSignal, setSelectedSignal] = useState<DecisionSignalItem | null>(null)

  const resetPage = useCallback(() => setPage(1), [])

  const queryParams: DecisionSignalListParams = {
    market: 'vn',
    page,
    pageSize: PAGE_SIZE,
    ...(filterAction ? { action: filterAction } : {}),
    ...(filterStatus ? { status: filterStatus } : {}),
    ...(scope === 'holding' ? { holdingOnly: true } : {}),
  }

  const fetchState = useSignals(queryParams, reloadKey)

  const handleScan = async (source: 'watchlist' | 'portfolio') => {
    if (scanning) return
    setScanning(true)
    try {
      const res = await decisionSignalsApi.scan(source)
      toast.success(
        `Đã quét ${res.scanned} mã · tạo ${res.created} tín hiệu` +
        (res.failed.length ? ` · ${res.failed.length} mã lỗi` : ''),
      )
      setReloadKey((k) => k + 1)
    } catch {
      toast.error('Quét tín hiệu thất bại. Vui lòng thử lại.')
    } finally {
      setScanning(false)
    }
  }
  const isLoading = fetchState.status === 'loading' || fetchState.status === 'idle'
  const isError = fetchState.status === 'error'
  const data = fetchState.status === 'success' ? fetchState.data : null

  const columns: ColumnDef<DecisionSignalItem>[] = [
    {
      id: 'stock',
      header: 'Mã / Tên',
      accessorKey: 'stockCode',
      cell: ({ row }) => (
        <div className="min-w-0">
          <p className="font-mono text-sm font-semibold text-foreground">{row.original.stockCode}</p>
          {row.original.stockName && (
            <p className="max-w-[120px] truncate text-xs text-muted-foreground">{row.original.stockName}</p>
          )}
        </div>
      ),
    },
    {
      id: 'action',
      header: VI.signals.action,
      accessorKey: 'action',
      cell: ({ row }) => (
        <span
          className={cn(
            'inline-block whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-semibold',
            actionToneClass(row.original.action),
          )}
        >
          {row.original.actionLabel || actionLabel(row.original.action)}
        </span>
      ),
    },
    {
      id: 'confidence',
      header: VI.signals.confidence,
      accessorKey: 'confidence',
      cell: ({ row }) => <ConfidenceBar value={row.original.confidence} />,
    },
    {
      id: 'score',
      header: VI.signals.score,
      accessorKey: 'score',
      cell: ({ row }) => (
        <span className="font-mono text-sm tabular-nums text-foreground">
          {row.original.score != null ? fmtNum(row.original.score, 1) : '--'}
        </span>
      ),
    },
    {
      id: 'entry',
      header: VI.signals.entry,
      enableSorting: false,
      cell: ({ row }) => {
        const { entryLow, entryHigh } = row.original
        if (entryLow == null && entryHigh == null)
          return <span className="text-muted-foreground">--</span>
        return (
          <span className="font-mono text-xs tabular-nums text-foreground">
            {entryLow != null && entryHigh != null
              ? `${fmtPrice(entryLow)} – ${fmtPrice(entryHigh)}`
              : entryLow != null
              ? fmtPrice(entryLow)
              : fmtPrice(entryHigh)}
          </span>
        )
      },
    },
    {
      id: 'stopLoss',
      header: VI.signals.stopLoss,
      accessorKey: 'stopLoss',
      cell: ({ row }) => (
        <span
          className={cn(
            'font-mono text-xs tabular-nums',
            row.original.stopLoss != null ? 'text-down' : 'text-muted-foreground',
          )}
        >
          {row.original.stopLoss != null ? fmtPrice(row.original.stopLoss) : '--'}
        </span>
      ),
    },
    {
      id: 'targetPrice',
      header: VI.signals.target,
      accessorKey: 'targetPrice',
      cell: ({ row }) => (
        <span
          className={cn(
            'font-mono text-xs tabular-nums',
            row.original.targetPrice != null ? 'text-up' : 'text-muted-foreground',
          )}
        >
          {row.original.targetPrice != null ? fmtPrice(row.original.targetPrice) : '--'}
        </span>
      ),
    },
    {
      id: 'status',
      header: VI.signals.status,
      accessorKey: 'status',
      cell: ({ row }) => (
        <span
          className={cn(
            'inline-block whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-semibold',
            statusBadgeClass(row.original.status),
          )}
        >
          {statusLabel(row.original.status)}
        </span>
      ),
    },
    {
      id: 'createdAt',
      header: 'Ngày',
      accessorKey: 'createdAt',
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">{formatDateShort(row.original.createdAt)}</span>
      ),
    },
  ]

  const table = useReactTable({
    data: data?.items ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,
    pageCount: data ? Math.ceil(data.total / PAGE_SIZE) : -1,
  })

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const hasFilter = !!filterAction || !!filterStatus

  return (
    <>
      <PageHeader
        title={VI.signals.title}
        subtitle="Danh sách tín hiệu giao dịch AI cho thị trường chứng khoán Việt Nam"
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void handleScan('watchlist')}
              disabled={scanning}
              title="Sinh tín hiệu kỹ thuật cho tất cả mã trong Danh mục theo dõi"
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-3.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {scanning ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Radar className="h-4 w-4" aria-hidden />}
              Quét mã theo dõi
            </button>
            <button
              type="button"
              onClick={() => void handleScan('portfolio')}
              disabled={scanning}
              title="Sinh tín hiệu cho cổ phiếu đang nắm giữ trong danh mục"
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-card px-3.5 text-sm font-medium text-foreground transition-colors hover:bg-secondary disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Radar className="h-4 w-4" aria-hidden /> Quét nắm giữ
            </button>
          </div>
        }
      />

      {/* Bộ lọc */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={scope}
          onChange={(e) => {
            setScope(e.target.value as 'all' | 'holding')
            resetPage()
          }}
          aria-label="Phạm vi tín hiệu"
          className={selectClass}
        >
          <option value="all">Tất cả tín hiệu</option>
          <option value="holding">Đang nắm giữ</option>
        </select>

        <select
          value={filterAction}
          onChange={(e) => {
            setFilterAction(e.target.value as DecisionAction | '')
            resetPage()
          }}
          aria-label="Lọc theo hành động"
          className={selectClass}
        >
          {ACTION_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        <select
          value={filterStatus}
          onChange={(e) => {
            setFilterStatus(e.target.value as DecisionSignalStatus | '')
            resetPage()
          }}
          aria-label="Lọc theo trạng thái"
          className={selectClass}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        {hasFilter && (
          <button
            type="button"
            onClick={() => {
              setFilterAction('')
              setFilterStatus('')
              setPage(1)
            }}
            className="flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm text-muted-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-3.5 w-3.5" />
            Xoá bộ lọc
          </button>
        )}

        {data && (
          <p className="ml-auto text-xs text-muted-foreground">
            {data.total} tín hiệu
          </p>
        )}
      </div>

      {/* Bảng dữ liệu */}
      <Card className="overflow-hidden">
        {isLoading ? (
          <TableSkeleton />
        ) : isError ? (
          <div className="flex flex-col items-center justify-center gap-2 p-10 text-center">
            <AlertTriangle className="h-7 w-7 text-danger" aria-hidden />
            <p className="text-sm text-danger">
              {fetchState.status === 'error' ? fetchState.message : 'Đã xảy ra lỗi khi tải tín hiệu.'}
            </p>
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <TrendingUp className="h-6 w-6" aria-hidden />
            </div>
            <p className="text-sm text-muted-foreground">{VI.signals.emptyState}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[780px] text-left">
              <thead>
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id} className="border-b border-border">
                    {headerGroup.headers.map((header) => {
                      const canSort = header.column.getCanSort()
                      const sortDir = header.column.getIsSorted()
                      return (
                        <th
                          key={header.id}
                          scope="col"
                          onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
                          className={cn(
                            'px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground',
                            'first:pl-4 last:pr-4',
                            canSort && 'cursor-pointer select-none hover:text-foreground',
                          )}
                        >
                          <span className="inline-flex items-center gap-1">
                            {flexRender(header.column.columnDef.header, header.getContext())}
                            {canSort && (
                              <span aria-hidden>
                                {sortDir === 'asc' ? (
                                  <ChevronUp className="h-3 w-3" />
                                ) : sortDir === 'desc' ? (
                                  <ChevronDown className="h-3 w-3" />
                                ) : (
                                  <ChevronsUpDown className="h-3 w-3 opacity-40" />
                                )}
                              </span>
                            )}
                          </span>
                        </th>
                      )
                    })}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => setSelectedSignal(row.original)}
                    tabIndex={0}
                    role="button"
                    aria-label={`Xem chi tiết tín hiệu ${row.original.stockCode}`}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelectedSignal(row.original)
                      }
                    }}
                    className={cn(
                      'cursor-pointer border-b border-border/50 transition-colors last:border-0',
                      'hover:bg-secondary/40 focus-visible:bg-secondary/40 focus-visible:outline-none',
                    )}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-3 py-2.5 first:pl-4 last:pr-4">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Phân trang */}
        {!isLoading && !isError && totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-border px-4 py-3">
            <p className="text-xs text-muted-foreground">
              {VI.common.page} {page} / {totalPages}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                aria-label="Trang trước"
                className="flex h-9 min-w-[44px] items-center justify-center rounded-lg border border-border bg-card px-3 text-sm text-foreground transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {VI.common.prev}
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                aria-label="Trang tiếp"
                className="flex h-9 min-w-[44px] items-center justify-center rounded-lg border border-border bg-card px-3 text-sm text-foreground transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {VI.common.next}
              </button>
            </div>
          </div>
        )}
      </Card>

      {/* Chú thích màu */}
      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="font-medium">Hành động:</span>
        <span className="rounded-md bg-up/15 px-2 py-0.5 text-up">Mua / Mua thêm</span>
        <span className="rounded-md bg-warning/15 px-2 py-0.5 text-warning">Giữ / Theo dõi</span>
        <span className="rounded-md bg-down/15 px-2 py-0.5 text-down">Bán / Tránh</span>
        <span className="ml-2">Nhấp vào hàng để xem chi tiết</span>
      </div>

      {/* Ngăn kéo chi tiết */}
      {selectedSignal && (
        <SignalDetailDrawer signal={selectedSignal} onClose={() => setSelectedSignal(null)} />
      )}
    </>
  )
}
