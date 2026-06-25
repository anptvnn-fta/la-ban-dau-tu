import { useState, useCallback } from 'react'
import {
  Loader2,
  AlertTriangle,
  PlayCircle,
  ChevronLeft,
  ChevronRight,
  Target,
  CheckCircle2,
  XCircle,
  BarChart2,
  TrendingUp,
  TrendingDown,
  Activity,
  Clock,
} from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardLabel } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { fmtNum, fmtPct } from '@/utils/num'
import { VI } from '@/strings/vi'
import { backtestApi } from '@/api/backtest'
import type { PerformanceMetrics, BacktestResultItem, BacktestResultsResponse } from '@/types/backtest'

// ─────────────────────────────────────────────
// Kiểu trạng thái
// ─────────────────────────────────────────────
type RunState =
  | { status: 'idle' }
  | { status: 'running' }
  | { status: 'done'; processed: number; saved: number }
  | { status: 'error'; message: string }

type PerfState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ok'; data: PerformanceMetrics }
  | { status: 'empty' }
  | { status: 'error'; message: string }

type ResultsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ok'; data: BacktestResultsResponse }
  | { status: 'empty' }
  | { status: 'error'; message: string }

// ─────────────────────────────────────────────
// Skeleton dòng bảng
// ─────────────────────────────────────────────
function SkeletonRow() {
  return (
    <tr className="border-b border-border">
      {[1, 2, 3, 4, 5, 6].map(i => (
        <td key={i} className="px-3 py-3">
          <div className="h-3 w-full animate-pulse rounded bg-secondary/60" />
        </td>
      ))}
    </tr>
  )
}

// ─────────────────────────────────────────────
// Skeleton card chỉ số
// ─────────────────────────────────────────────
function StatCardSkeleton() {
  return (
    <Card className="p-4 space-y-2">
      <div className="h-3 w-24 animate-pulse rounded bg-secondary/60" />
      <div className="h-7 w-16 animate-pulse rounded bg-secondary/60" />
    </Card>
  )
}

// ─────────────────────────────────────────────
// Card chỉ số hiệu suất
// ─────────────────────────────────────────────
function StatCard({
  label,
  value,
  sub,
  icon,
  tone,
}: {
  label: string
  value: string
  sub?: string
  icon: React.ReactNode
  tone?: 'up' | 'down' | 'flat' | 'warn'
}) {
  const toneClass =
    tone === 'up'
      ? 'text-up'
      : tone === 'down'
        ? 'text-down'
        : tone === 'warn'
          ? 'text-warning'
          : 'text-foreground'

  return (
    <Card className="p-4 flex flex-col gap-2">
      <CardLabel icon={icon}>{label}</CardLabel>
      <p className={cn('font-mono text-2xl font-bold tabular-nums', toneClass)}>{value}</p>
      {sub ? <p className="text-xs text-muted-foreground">{sub}</p> : null}
    </Card>
  )
}

// ─────────────────────────────────────────────
// Badge Đúng / Sai
// ─────────────────────────────────────────────
function CorrectBadge({ correct }: { correct?: boolean | null }) {
  if (correct === true) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-up/10 px-2 py-0.5 text-xs font-semibold text-up">
        <CheckCircle2 className="h-3 w-3" aria-hidden />
        Đúng
      </span>
    )
  }
  if (correct === false) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-down/10 px-2 py-0.5 text-xs font-semibold text-down">
        <XCircle className="h-3 w-3" aria-hidden />
        Sai
      </span>
    )
  }
  return <span className="text-xs text-muted-foreground">—</span>
}

// ─────────────────────────────────────────────
// Badge kết quả đánh giá
// ─────────────────────────────────────────────
function OutcomeBadge({ outcome }: { outcome?: string }) {
  if (!outcome) return <span className="text-xs text-muted-foreground">—</span>

  const map: Record<string, { label: string; className: string }> = {
    win: { label: 'Thắng', className: 'bg-up/10 text-up' },
    loss: { label: 'Thua', className: 'bg-down/10 text-down' },
    neutral: { label: 'Trung tính', className: 'bg-secondary text-secondary-foreground' },
    insufficient: { label: 'Thiếu dữ liệu', className: 'bg-warning/10 text-warning' },
  }

  const cfg = map[outcome.toLowerCase()]
  if (!cfg) {
    return (
      <span className="inline-flex rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
        {outcome}
      </span>
    )
  }

  return (
    <span className={cn('inline-flex rounded-full px-2 py-0.5 text-xs font-semibold', cfg.className)}>
      {cfg.label}
    </span>
  )
}

// ─────────────────────────────────────────────
// Dòng bảng kết quả
// ─────────────────────────────────────────────
function ResultRow({ item }: { item: BacktestResultItem }) {
  const dateStr = item.analysisDate
    ? new Date(item.analysisDate).toLocaleDateString('vi-VN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      })
    : '--'

  const forecastLabel = item.directionExpected
    ? item.directionExpected === 'up'
      ? 'Tăng'
      : item.directionExpected === 'down'
        ? 'Giảm'
        : item.directionExpected
    : item.actionLabel ?? item.trendPrediction ?? '--'

  const actualLabel = item.actualMovement
    ? item.actualMovement === 'up'
      ? 'Tăng'
      : item.actualMovement === 'down'
        ? 'Giảm'
        : item.actualMovement
    : '--'

  const actualClass =
    item.actualMovement === 'up'
      ? 'text-up'
      : item.actualMovement === 'down'
        ? 'text-down'
        : 'text-muted-foreground'

  return (
    <tr className="border-b border-border transition-colors hover:bg-secondary/20">
      <td className="px-3 py-3">
        <span className="font-mono text-sm font-bold text-foreground">{item.code}</span>
        {item.stockName && (
          <span className="ml-1.5 text-xs text-muted-foreground">{item.stockName}</span>
        )}
      </td>
      <td className="px-3 py-3 font-mono text-xs text-muted-foreground tabular-nums">{dateStr}</td>
      <td className="px-3 py-3 text-sm text-foreground">{forecastLabel}</td>
      <td className={cn('px-3 py-3 text-sm font-medium', actualClass)}>{actualLabel}</td>
      <td className="px-3 py-3">
        <CorrectBadge correct={item.directionCorrect} />
      </td>
      <td className="px-3 py-3">
        <OutcomeBadge outcome={item.outcome} />
      </td>
    </tr>
  )
}

// ─────────────────────────────────────────────
// Trang chính
// ─────────────────────────────────────────────
export default function DanhGiaDuBaoPage() {
  const [codeInput, setCodeInput] = useState('')
  const [windowDays, setWindowDays] = useState<number>(10)
  const [runState, setRunState] = useState<RunState>({ status: 'idle' })
  const [perfState, setPerfState] = useState<PerfState>({ status: 'idle' })
  const [resultsState, setResultsState] = useState<ResultsState>({ status: 'idle' })
  const [currentPage, setCurrentPage] = useState(1)

  const PAGE_SIZE = 20

  const loadData = useCallback(
    async (page = 1) => {
      const code = codeInput.trim().toUpperCase() || undefined

      setPerfState({ status: 'loading' })
      try {
        const perf = code
          ? await backtestApi.getStockPerformance(code, { evalWindowDays: windowDays })
          : await backtestApi.getOverallPerformance({ evalWindowDays: windowDays })

        if (!perf) {
          setPerfState({ status: 'empty' })
        } else {
          setPerfState({ status: 'ok', data: perf })
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : VI.errors.generic
        setPerfState({ status: 'error', message: msg })
      }

      setResultsState({ status: 'loading' })
      try {
        const res = await backtestApi.getResults({
          code,
          evalWindowDays: windowDays,
          page,
          limit: PAGE_SIZE,
        })
        if (res.total === 0) {
          setResultsState({ status: 'empty' })
        } else {
          setResultsState({ status: 'ok', data: res })
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : VI.errors.generic
        setResultsState({ status: 'error', message: msg })
      }
    },
    [codeInput, windowDays],
  )

  const handleRun = async () => {
    const code = codeInput.trim().toUpperCase() || undefined
    setRunState({ status: 'running' })
    try {
      const res = await backtestApi.run({ code, evalWindowDays: windowDays })
      setRunState({ status: 'done', processed: res.processed, saved: res.saved })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : VI.errors.generic
      setRunState({ status: 'error', message: msg })
    }
    setCurrentPage(1)
    await loadData(1)
  }

  const handlePage = async (page: number) => {
    setCurrentPage(page)
    await loadData(page)
  }

  const isRunning = runState.status === 'running'
  const totalPages =
    resultsState.status === 'ok'
      ? Math.ceil(resultsState.data.total / PAGE_SIZE)
      : 0

  return (
    <>
      <PageHeader
        title={VI.backtest.title}
        subtitle={VI.backtest.subtitle}
      />

      {/* ── Thanh điều khiển ── */}
      <Card className="mb-6 p-4">
        <div className="flex flex-wrap items-end gap-4">
          {/* Mã cổ phiếu */}
          <div className="flex flex-col gap-1">
            <label
              htmlFor="bt-code"
              className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
            >
              Mã cổ phiếu (tùy chọn)
            </label>
            <input
              id="bt-code"
              type="text"
              value={codeInput}
              onChange={e => setCodeInput(e.target.value.toUpperCase())}
              placeholder="Ví dụ: VCB"
              maxLength={10}
              className={cn(
                'h-10 w-36 rounded-lg border border-border bg-background px-3 text-sm font-mono font-semibold uppercase',
                'text-foreground placeholder:font-normal placeholder:normal-case placeholder:text-muted-foreground',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              )}
            />
          </div>

          {/* Cửa sổ đánh giá */}
          <div className="flex flex-col gap-1">
            <label
              htmlFor="bt-window"
              className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
            >
              {VI.backtest.window}
            </label>
            <input
              id="bt-window"
              type="number"
              min={1}
              max={90}
              value={windowDays}
              onChange={e => setWindowDays(Math.max(1, parseInt(e.target.value) || 10))}
              className={cn(
                'h-10 w-24 rounded-lg border border-border bg-background px-3 text-sm font-mono tabular-nums',
                'text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              )}
            />
          </div>

          {/* Nút chạy đánh giá */}
          <button
            type="button"
            onClick={handleRun}
            disabled={isRunning}
            aria-label="Chạy đánh giá độ chính xác dự báo"
            className={cn(
              'inline-flex h-10 min-w-[140px] items-center justify-center gap-2 rounded-lg px-4',
              'bg-primary text-primary-foreground text-sm font-semibold',
              'transition-colors hover:bg-primary/90 disabled:opacity-50',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            )}
          >
            {isRunning ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <PlayCircle className="h-4 w-4" aria-hidden />
            )}
            {VI.backtest.run}
          </button>

          {/* Thông báo sau khi chạy */}
          {runState.status === 'done' && (
            <p className="text-sm text-muted-foreground">
              Đã xử lý{' '}
              <span className="font-semibold text-foreground">{runState.processed}</span> dự báo,
              lưu{' '}
              <span className="font-semibold text-foreground">{runState.saved}</span> kết quả mới.
            </p>
          )}
          {runState.status === 'error' && (
            <p className="flex items-center gap-1 text-sm text-danger">
              <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
              {runState.message}
            </p>
          )}
        </div>
      </Card>

      {/* ── Chỉ số hiệu suất ── */}
      <section aria-label="Chỉ số hiệu suất tổng thể" className="mb-6">
        <h2 className="mb-3 font-heading text-base font-semibold text-foreground">
          Hiệu suất tổng thể
        </h2>

        {perfState.status === 'idle' && (
          <p className="text-sm text-muted-foreground">{VI.backtest.emptyState}</p>
        )}

        {perfState.status === 'loading' && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {Array.from({ length: 8 }).map((_, i) => (
              <StatCardSkeleton key={i} />
            ))}
          </div>
        )}

        {perfState.status === 'error' && (
          <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-4 text-sm text-danger">
            <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden />
            {perfState.message}
          </div>
        )}

        {perfState.status === 'empty' && (
          <p className="text-sm text-muted-foreground">{VI.common.noData}</p>
        )}

        {perfState.status === 'ok' && (() => {
          const m = perfState.data
          const accuracyTone: 'up' | 'flat' | 'down' =
            (m.directionAccuracyPct ?? 0) >= 60
              ? 'up'
              : (m.directionAccuracyPct ?? 0) >= 40
                ? 'flat'
                : 'down'
          const winTone: 'up' | 'flat' | 'down' =
            (m.winRatePct ?? 0) >= 50 ? 'up' : (m.winRatePct ?? 0) >= 30 ? 'flat' : 'down'
          const avgReturnTone: 'up' | 'flat' | 'down' =
            (m.avgStockReturnPct ?? 0) > 0
              ? 'up'
              : (m.avgStockReturnPct ?? 0) < 0
                ? 'down'
                : 'flat'
          const simReturnTone: 'up' | 'flat' | 'down' =
            (m.avgSimulatedReturnPct ?? 0) > 0
              ? 'up'
              : (m.avgSimulatedReturnPct ?? 0) < 0
                ? 'down'
                : 'flat'

          return (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              <StatCard
                label="Tổng số dự báo"
                value={fmtNum(m.totalEvaluations, 0)}
                sub={`${fmtNum(m.completedCount, 0)} hoàn thành`}
                icon={<Target className="h-3 w-3" />}
              />
              <StatCard
                label="Độ chính xác hướng"
                value={m.directionAccuracyPct != null ? `${fmtNum(m.directionAccuracyPct, 1)}%` : '--'}
                sub="Dự báo tăng/giảm đúng"
                icon={<Activity className="h-3 w-3" />}
                tone={accuracyTone}
              />
              <StatCard
                label="Tỉ lệ thắng"
                value={m.winRatePct != null ? `${fmtNum(m.winRatePct, 1)}%` : '--'}
                sub={`${fmtNum(m.winCount, 0)} thắng / ${fmtNum(m.lossCount, 0)} thua`}
                icon={<CheckCircle2 className="h-3 w-3" />}
                tone={winTone}
              />
              <StatCard
                label="Lợi nhuận TB cổ phiếu"
                value={m.avgStockReturnPct != null ? fmtPct(m.avgStockReturnPct) : '--'}
                sub="Thực tế trong cửa sổ"
                icon={<TrendingUp className="h-3 w-3" />}
                tone={avgReturnTone}
              />
              <StatCard
                label="LN mô phỏng TB"
                value={m.avgSimulatedReturnPct != null ? fmtPct(m.avgSimulatedReturnPct) : '--'}
                sub="Mô phỏng vào/ra lệnh"
                icon={<BarChart2 className="h-3 w-3" />}
                tone={simReturnTone}
              />
              <StatCard
                label="Tỉ lệ cắt lỗ kích hoạt"
                value={
                  m.stopLossTriggerRate != null
                    ? `${fmtNum(m.stopLossTriggerRate * 100, 1)}%`
                    : '--'
                }
                icon={<TrendingDown className="h-3 w-3" />}
                tone="down"
              />
              <StatCard
                label="Tỉ lệ chốt lời kích hoạt"
                value={
                  m.takeProfitTriggerRate != null
                    ? `${fmtNum(m.takeProfitTriggerRate * 100, 1)}%`
                    : '--'
                }
                icon={<TrendingUp className="h-3 w-3" />}
                tone="up"
              />
              <StatCard
                label="Số ngày TB đến điểm chạm"
                value={m.avgDaysToFirstHit != null ? fmtNum(m.avgDaysToFirstHit, 1) : '--'}
                sub="ngày giao dịch"
                icon={<Clock className="h-3 w-3" />}
              />
            </div>
          )
        })()}
      </section>

      {/* ── Bảng kết quả ── */}
      <section aria-label="Bảng kết quả đánh giá">
        <h2 className="mb-3 font-heading text-base font-semibold text-foreground">
          {VI.backtest.results}
        </h2>

        {resultsState.status === 'idle' && (
          <div className="flex min-h-[200px] items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 p-8 text-center">
            <p className="text-sm text-muted-foreground">{VI.backtest.emptyState}</p>
          </div>
        )}

        {resultsState.status === 'empty' && (
          <div className="flex min-h-[200px] items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 p-8 text-center">
            <p className="text-sm text-muted-foreground">{VI.backtest.emptyState}</p>
          </div>
        )}

        {resultsState.status === 'error' && (
          <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-4 text-sm text-danger">
            <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden />
            {resultsState.message}
          </div>
        )}

        {(resultsState.status === 'loading' || resultsState.status === 'ok') && (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table
                className="w-full min-w-[700px] text-sm"
                aria-label="Bảng kết quả kiểm định dự báo"
              >
                <thead>
                  <tr className="border-b border-border bg-secondary/30 text-left">
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Mã
                    </th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Ngày phân tích
                    </th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Dự báo
                    </th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Kết quả thực tế
                    </th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Đúng/Sai
                    </th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Kết quả
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {resultsState.status === 'loading'
                    ? Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
                    : resultsState.data.items.map((item: BacktestResultItem) => (
                        <ResultRow key={item.analysisHistoryId} item={item} />
                      ))}
                </tbody>
              </table>
            </div>

            {/* Phân trang */}
            {resultsState.status === 'ok' && totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-border px-4 py-3">
                <p className="text-xs text-muted-foreground">
                  {VI.common.total}:{' '}
                  <span className="font-semibold text-foreground">
                    {fmtNum(resultsState.data.total, 0)}
                  </span>{' '}
                  kết quả — {VI.common.page}{' '}
                  <span className="font-semibold text-foreground">{currentPage}</span> /{' '}
                  {totalPages}
                </p>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => handlePage(currentPage - 1)}
                    disabled={currentPage <= 1}
                    aria-label="Trang trước"
                    className={cn(
                      'flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground',
                      'hover:bg-secondary disabled:opacity-40',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    )}
                  >
                    <ChevronLeft className="h-4 w-4" aria-hidden />
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePage(currentPage + 1)}
                    disabled={currentPage >= totalPages}
                    aria-label="Trang tiếp theo"
                    className={cn(
                      'flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground',
                      'hover:bg-secondary disabled:opacity-40',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    )}
                  >
                    <ChevronRight className="h-4 w-4" aria-hidden />
                  </button>
                </div>
              </div>
            )}
          </Card>
        )}
      </section>
    </>
  )
}
