import { useState, useEffect } from 'react'
import { Loader2, AlertTriangle, Cpu, Zap, Activity, Clock, Hash, List } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardLabel } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { fmtNum, fmtCompact } from '@/utils/num'
import { VI } from '@/strings/vi'
import { usageApi, type UsagePeriod, type UsageDashboard, type UsageModelBreakdown, type UsageCallTypeBreakdown, type UsageCallRecord } from '@/api/usage'

// ─── Nhãn cho các loại tác vụ ───────────────────────────────────────────────
function labelCallType(callType: string): string {
  const map: Record<string, string> = {
    analyze: 'Phân tích cổ phiếu',
    market_review: 'Diễn biến thị trường',
    chat: 'Trợ lý AI',
    backtest: 'Đánh giá dự báo',
    signal: 'Tín hiệu AI',
  }
  return map[callType] ?? callType
}

// ─── Định dạng thời gian ─────────────────────────────────────────────────────
function fmtDateTime(iso: string): string {
  try {
    const d = new Date(iso)
    return new Intl.DateTimeFormat('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d)
  } catch {
    return iso
  }
}

// ─── Thanh ngang mini ────────────────────────────────────────────────────────
function MiniBar({ value, max, className }: { value: number; max: number; className?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="h-1.5 w-full rounded-full bg-secondary">
      <div
        className={cn('h-1.5 rounded-full', className ?? 'bg-primary')}
        style={{ width: `${pct}%` }}
        aria-hidden="true"
      />
    </div>
  )
}

// ─── Skeleton loading ─────────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <Card className="p-5 space-y-3 animate-pulse">
      <div className="h-3 w-24 rounded bg-secondary" />
      <div className="h-7 w-32 rounded bg-secondary" />
    </Card>
  )
}

function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-8 rounded bg-secondary" />
      ))}
    </div>
  )
}

// ─── Thẻ tóm tắt ─────────────────────────────────────────────────────────────
function SummaryCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode
  label: string
  value: string
  sub?: string
}) {
  return (
    <Card className="p-5 flex flex-col gap-3">
      <CardLabel icon={icon}>{label}</CardLabel>
      <p className="font-mono text-3xl font-bold tabular-nums text-foreground">{value}</p>
      {sub ? <p className="text-xs text-muted-foreground">{sub}</p> : null}
    </Card>
  )
}

// ─── Bảng theo mô hình ───────────────────────────────────────────────────────
function ByModelTable({ rows }: { rows: UsageModelBreakdown[] }) {
  if (rows.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">{VI.common.noData}</p>
  }
  const maxTokens = Math.max(...rows.map((r) => r.totalTokens), 1)
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="pb-2 pr-4 font-semibold">Mô hình</th>
            <th className="pb-2 pr-4 text-right font-semibold">Lượt gọi</th>
            <th className="pb-2 pr-4 text-right font-semibold">Prompt</th>
            <th className="pb-2 pr-4 text-right font-semibold">Completion</th>
            <th className="pb-2 font-semibold">Tổng token</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr key={row.model} className="group">
              <td className="py-2.5 pr-4 font-mono text-xs text-foreground">{row.model}</td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums text-foreground">
                {fmtNum(row.calls, 0)}
              </td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums text-muted-foreground">
                {fmtCompact(row.promptTokens)}
              </td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums text-muted-foreground">
                {fmtCompact(row.completionTokens)}
              </td>
              <td className="py-2.5 min-w-[140px]">
                <div className="flex items-center gap-2">
                  <span className="font-mono tabular-nums text-foreground">
                    {fmtCompact(row.totalTokens)}
                  </span>
                  <div className="flex-1">
                    <MiniBar value={row.totalTokens} max={maxTokens} />
                  </div>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Bảng theo loại tác vụ ───────────────────────────────────────────────────
function ByCallTypeTable({ rows }: { rows: UsageCallTypeBreakdown[] }) {
  if (rows.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">{VI.common.noData}</p>
  }
  const maxTokens = Math.max(...rows.map((r) => r.totalTokens), 1)
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="pb-2 pr-4 font-semibold">Loại tác vụ</th>
            <th className="pb-2 pr-4 text-right font-semibold">Lượt gọi</th>
            <th className="pb-2 pr-4 text-right font-semibold">Prompt</th>
            <th className="pb-2 pr-4 text-right font-semibold">Completion</th>
            <th className="pb-2 font-semibold">Tổng token</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr key={row.callType}>
              <td className="py-2.5 pr-4 text-foreground">{labelCallType(row.callType)}</td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums text-foreground">
                {fmtNum(row.calls, 0)}
              </td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums text-muted-foreground">
                {fmtCompact(row.promptTokens)}
              </td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums text-muted-foreground">
                {fmtCompact(row.completionTokens)}
              </td>
              <td className="py-2.5 min-w-[140px]">
                <div className="flex items-center gap-2">
                  <span className="font-mono tabular-nums text-foreground">
                    {fmtCompact(row.totalTokens)}
                  </span>
                  <div className="flex-1">
                    <MiniBar value={row.totalTokens} max={maxTokens} className="bg-primary/70" />
                  </div>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Bảng lượt gọi gần đây ───────────────────────────────────────────────────
function RecentCallsTable({ rows }: { rows: UsageCallRecord[] }) {
  if (rows.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">{VI.common.noData}</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="pb-2 pr-4 font-semibold">Thời gian</th>
            <th className="pb-2 pr-4 font-semibold">Loại tác vụ</th>
            <th className="pb-2 pr-4 font-semibold">Mô hình</th>
            <th className="pb-2 pr-4 font-semibold">Mã CP</th>
            <th className="pb-2 pr-4 text-right font-semibold">Prompt</th>
            <th className="pb-2 pr-4 text-right font-semibold">Completion</th>
            <th className="pb-2 text-right font-semibold">Tổng</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr key={row.id} className="hover:bg-secondary/40 transition-colors">
              <td className="py-2 pr-4 font-mono text-xs text-muted-foreground whitespace-nowrap">
                {fmtDateTime(row.calledAt)}
              </td>
              <td className="py-2 pr-4 text-foreground whitespace-nowrap">
                {labelCallType(row.callType)}
              </td>
              <td className="py-2 pr-4 font-mono text-xs text-muted-foreground whitespace-nowrap">
                {row.model}
              </td>
              <td className="py-2 pr-4">
                {row.stockCode ? (
                  <span className="inline-block rounded bg-secondary px-1.5 py-0.5 font-mono text-xs font-semibold text-foreground">
                    {row.stockCode}
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
              <td className="py-2 pr-4 text-right font-mono tabular-nums text-muted-foreground">
                {fmtCompact(row.promptTokens)}
              </td>
              <td className="py-2 pr-4 text-right font-mono tabular-nums text-muted-foreground">
                {fmtCompact(row.completionTokens)}
              </td>
              <td className="py-2 text-right font-mono tabular-nums font-semibold text-foreground">
                {fmtCompact(row.totalTokens)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Công tắc kỳ ─────────────────────────────────────────────────────────────
const PERIODS: { value: UsagePeriod; label: string }[] = [
  { value: 'today', label: VI.usage.today },
  { value: 'month', label: VI.usage.month },
  { value: 'all', label: VI.usage.allTime },
]

// ─── Trang chính ─────────────────────────────────────────────────────────────
export default function SuDungTokenPage() {
  const [period, setPeriod] = useState<UsagePeriod>('month')
  const [data, setData] = useState<UsageDashboard | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    usageApi
      .getDashboard({ period, limit: 50 })
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch(() => {
        if (!cancelled) setError('Không thể tải dữ liệu sử dụng. Vui lòng thử lại.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [period])

  const periodSwitcher = (
    <div
      role="group"
      aria-label="Chọn kỳ thống kê"
      className="flex items-center rounded-lg border border-border bg-card p-0.5"
    >
      {PERIODS.map((p) => (
        <button
          key={p.value}
          type="button"
          onClick={() => setPeriod(p.value)}
          aria-pressed={period === p.value}
          className={cn(
            'min-h-[44px] rounded-md px-4 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            period === p.value
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {p.label}
        </button>
      ))}
    </div>
  )

  return (
    <>
      <PageHeader
        title={VI.usage.title}
        subtitle="Theo dõi mức tiêu thụ token AI theo thời gian"
        actions={periodSwitcher}
      />

      {/* Trạng thái lỗi */}
      {error ? (
        <Card className="flex h-48 flex-col items-center justify-center gap-2 text-center">
          <AlertTriangle className="h-7 w-7 text-danger" />
          <p className="text-sm text-danger">{error}</p>
          <button
            type="button"
            onClick={() => setPeriod((p) => p)}
            className="mt-1 min-h-[44px] rounded-lg border border-border bg-card px-4 text-sm font-medium hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {VI.common.retry}
          </button>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Thẻ tóm tắt */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {loading ? (
              <>
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
              </>
            ) : (
              <>
                <SummaryCard
                  icon={<Activity className="h-3.5 w-3.5" />}
                  label={VI.usage.totalCalls}
                  value={fmtNum(data?.totalCalls ?? 0, 0)}
                />
                <SummaryCard
                  icon={<Hash className="h-3.5 w-3.5" />}
                  label={VI.usage.totalTokens}
                  value={fmtCompact(data?.totalTokens ?? 0)}
                  sub={`Prompt: ${fmtCompact(data?.totalPromptTokens ?? 0)} · Completion: ${fmtCompact(data?.totalCompletionTokens ?? 0)}`}
                />
                <SummaryCard
                  icon={<Zap className="h-3.5 w-3.5" />}
                  label="Token prompt"
                  value={fmtCompact(data?.totalPromptTokens ?? 0)}
                />
                <SummaryCard
                  icon={<Cpu className="h-3.5 w-3.5" />}
                  label="Token completion"
                  value={fmtCompact(data?.totalCompletionTokens ?? 0)}
                />
              </>
            )}
          </div>

          {/* Phân tách 2 cột: Theo mô hình + Theo loại tác vụ */}
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            {/* Theo mô hình */}
            <Card className="p-5 space-y-4">
              <CardLabel icon={<Cpu className="h-3.5 w-3.5" />}>{VI.usage.byModel}</CardLabel>
              {loading ? (
                <SkeletonTable rows={3} />
              ) : (
                <ByModelTable rows={data?.byModel ?? []} />
              )}
            </Card>

            {/* Theo loại tác vụ */}
            <Card className="p-5 space-y-4">
              <CardLabel icon={<List className="h-3.5 w-3.5" />}>{VI.usage.byCallType}</CardLabel>
              {loading ? (
                <SkeletonTable rows={3} />
              ) : (
                <ByCallTypeTable rows={data?.byCallType ?? []} />
              )}
            </Card>
          </div>

          {/* Lượt gọi gần đây */}
          <Card className="p-5 space-y-4">
            <CardLabel icon={<Clock className="h-3.5 w-3.5" />}>{VI.usage.recentCalls}</CardLabel>
            {loading ? (
              <SkeletonTable rows={8} />
            ) : (
              <RecentCallsTable rows={data?.recentCalls ?? []} />
            )}
          </Card>
        </div>
      )}
    </>
  )
}
