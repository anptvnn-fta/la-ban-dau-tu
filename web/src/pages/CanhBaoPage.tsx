import { useState, useEffect, useCallback, type ReactNode } from 'react'
import {
  Bell,
  BellOff,
  Plus,
  Trash2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  XCircle,
  Loader2,
} from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardLabel } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { alertsApi } from '@/api/alerts'
import { VI } from '@/strings/vi'
import type {
  AlertType,
  AlertSeverity,
  AlertTargetScope,
  AlertDirection,
  AlertRuleCreateRequest,
  AlertRuleItem,
  AlertTriggerItem,
} from '@/types/alerts'

// ─── Loại cảnh báo được hiển thị (bỏ market_light_status & market_light_score_drop) ───
const ALLOWED_TYPES: { value: AlertType; label: string }[] = [
  { value: 'price_cross', label: 'Giá cắt mốc' },
  { value: 'price_change_percent', label: 'Biến động %' },
  { value: 'volume_spike', label: 'Đột biến KL' },
  { value: 'ma_price_cross', label: 'Giá cắt MA' },
  { value: 'rsi_threshold', label: 'RSI ngưỡng' },
  { value: 'macd_cross', label: 'MACD cắt' },
]

function labelForType(t: AlertType): string {
  return ALLOWED_TYPES.find((x) => x.value === t)?.label ?? t
}

// ─── Mức độ ────────────────────────────────────────────────────────────────────
const SEVERITY_MAP: Record<AlertSeverity, { label: string; cls: string }> = {
  info: { label: 'Thông tin', cls: 'text-foreground bg-secondary' },
  warning: { label: 'Cảnh báo', cls: 'text-warning bg-warning/10' },
  critical: { label: 'Nghiêm trọng', cls: 'text-danger bg-danger/10' },
}

// ─── Hướng ─────────────────────────────────────────────────────────────────────
const DIRECTION_MAP: Record<AlertDirection, string> = {
  above: 'Vượt trên',
  below: 'Xuống dưới',
  up: 'Tăng',
  down: 'Giảm',
  bullish_cross: 'Cắt lên (tăng)',
  bearish_cross: 'Cắt xuống (giảm)',
}

// ─── Trạng thái kích hoạt ──────────────────────────────────────────────────────
function triggerBadge(status: string): { label: string; icon: ReactNode; cls: string } {
  switch (status) {
    case 'triggered':
      return { label: 'Đã kích hoạt', icon: <CheckCircle2 className="h-3.5 w-3.5" />, cls: 'text-up bg-up/10' }
    case 'skipped':
      return { label: 'Bỏ qua', icon: <Clock className="h-3.5 w-3.5" />, cls: 'text-muted-foreground bg-secondary' }
    case 'degraded':
      return { label: 'Suy giảm', icon: <AlertTriangle className="h-3.5 w-3.5" />, cls: 'text-warning bg-warning/10' }
    case 'failed':
      return { label: 'Thất bại', icon: <XCircle className="h-3.5 w-3.5" />, cls: 'text-danger bg-danger/10' }
    default:
      return { label: status, icon: null, cls: 'text-muted-foreground bg-secondary' }
  }
}

// ─── Nhỏ ───────────────────────────────────────────────────────────────────────
function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold', className)}>
      {children}
    </span>
  )
}

function IconBtn({
  onClick,
  title,
  disabled,
  children,
  variant = 'default',
}: {
  onClick: () => void
  title: string
  disabled?: boolean
  children: ReactNode
  variant?: 'default' | 'danger'
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={title}
      title={title}
      className={cn(
        'flex h-8 w-8 items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40',
        variant === 'danger'
          ? 'text-danger hover:bg-danger/10'
          : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}

function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr className="animate-pulse border-b border-border">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-3 py-3">
          <div className="h-4 rounded bg-secondary" />
        </td>
      ))}
    </tr>
  )
}

// ─── Form tham số cần thiết theo loại ─────────────────────────────────────────
function paramsForType(type: AlertType): string[] {
  switch (type) {
    case 'price_cross':        return ['direction', 'price']
    case 'price_change_percent': return ['direction', 'changePct']
    case 'volume_spike':       return ['multiplier', 'window']
    case 'ma_price_cross':     return ['direction', 'period']
    case 'rsi_threshold':      return ['direction', 'threshold', 'period']
    case 'macd_cross':         return ['direction']
    default:                   return []
  }
}

const SCOPE_OPTIONS: { value: AlertTargetScope; label: string }[] = [
  { value: 'single_symbol', label: 'Mã cụ thể' },
  { value: 'watchlist', label: 'Danh sách theo dõi' },
  { value: 'portfolio_holdings', label: 'Cổ phiếu danh mục' },
]

const SEVERITY_OPTIONS: { value: AlertSeverity; label: string }[] = [
  { value: 'info', label: 'Thông tin' },
  { value: 'warning', label: 'Cảnh báo' },
  { value: 'critical', label: 'Nghiêm trọng' },
]

const DIRECTION_OPTIONS: { value: AlertDirection; label: string }[] = [
  { value: 'above', label: 'Vượt trên' },
  { value: 'below', label: 'Xuống dưới' },
  { value: 'up', label: 'Tăng' },
  { value: 'down', label: 'Giảm' },
  { value: 'bullish_cross', label: 'Cắt lên (tăng)' },
  { value: 'bearish_cross', label: 'Cắt xuống (giảm)' },
]

interface FormState {
  name: string
  targetScope: AlertTargetScope
  target: string
  alertType: AlertType
  severity: AlertSeverity
  direction: AlertDirection | ''
  price: string
  changePct: string
  threshold: string
  period: string
  multiplier: string
  window: string
}

const INITIAL_FORM: FormState = {
  name: '',
  targetScope: 'single_symbol',
  target: '',
  alertType: 'price_cross',
  severity: 'warning',
  direction: 'above',
  price: '',
  changePct: '',
  threshold: '',
  period: '14',
  multiplier: '2',
  window: '20',
}

function labelCls() {
  return 'block text-xs font-semibold text-muted-foreground mb-1'
}

function inputCls(err?: boolean) {
  return cn(
    'w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
    err && 'border-danger',
  )
}

function selectCls() {
  return 'w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
}

// ─── Form thêm quy tắc ─────────────────────────────────────────────────────────
function AddRuleForm({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState<FormState>(INITIAL_FORM)
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const needed = paramsForType(form.alertType)

  function set<K extends keyof FormState>(k: K, v: FormState[K]) {
    setForm((prev) => ({ ...prev, [k]: v }))
    setErrors((prev) => ({ ...prev, [k]: undefined }))
  }

  function validate(): boolean {
    const e: Partial<Record<keyof FormState, string>> = {}
    if (!form.target.trim()) e.target = 'Vui lòng nhập mã / đối tượng'
    if (needed.includes('price') && !form.price) e.price = 'Nhập mức giá'
    if (needed.includes('changePct') && !form.changePct) e.changePct = 'Nhập % biến động'
    if (needed.includes('threshold') && !form.threshold) e.threshold = 'Nhập ngưỡng'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    const parameters: AlertRuleCreateRequest['parameters'] = {}
    if (needed.includes('direction') && form.direction) parameters.direction = form.direction as AlertDirection
    if (needed.includes('price') && form.price) parameters.price = parseFloat(form.price)
    if (needed.includes('changePct') && form.changePct) parameters.changePct = parseFloat(form.changePct)
    if (needed.includes('threshold') && form.threshold) parameters.threshold = parseFloat(form.threshold)
    if (needed.includes('period') && form.period) parameters.period = parseInt(form.period)
    if (needed.includes('multiplier') && form.multiplier) parameters.multiplier = parseFloat(form.multiplier)
    if (needed.includes('window') && form.window) parameters.window = parseInt(form.window)

    const payload: AlertRuleCreateRequest = {
      name: form.name.trim() || undefined,
      targetScope: form.targetScope,
      target: form.target.trim().toUpperCase(),
      alertType: form.alertType,
      parameters,
      severity: form.severity,
      enabled: true,
    }

    setSaving(true)
    setSaveError(null)
    try {
      await alertsApi.createRule(payload)
      onSuccess()
    } catch (err) {
      setSaveError((err as Error)?.message ?? 'Không thể tạo quy tắc. Vui lòng thử lại.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="mb-5 p-5">
      <h2 className="mb-4 font-heading text-base font-semibold text-foreground">Thêm quy tắc cảnh báo</h2>
      <form onSubmit={handleSubmit} noValidate>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className={labelCls()}>Tên quy tắc (tùy chọn)</label>
            <input
              className={inputCls()}
              placeholder="VD: VNM vượt 80.000"
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
            />
          </div>

          <div>
            <label className={labelCls()}>Loại cảnh báo</label>
            <select
              className={selectCls()}
              value={form.alertType}
              onChange={(e) => { set('alertType', e.target.value as AlertType); setErrors({}) }}
            >
              {ALLOWED_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className={labelCls()}>Mức độ</label>
            <select className={selectCls()} value={form.severity} onChange={(e) => set('severity', e.target.value as AlertSeverity)}>
              {SEVERITY_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>

          <div>
            <label className={labelCls()}>Phạm vi</label>
            <select className={selectCls()} value={form.targetScope} onChange={(e) => set('targetScope', e.target.value as AlertTargetScope)}>
              {SCOPE_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>

          <div>
            <label className={labelCls()}>Mã / Đối tượng</label>
            <input
              className={inputCls(!!errors.target)}
              placeholder="VD: VNM, VCB..."
              value={form.target}
              onChange={(e) => set('target', e.target.value)}
            />
            {errors.target && <p className="mt-1 text-xs text-danger">{errors.target}</p>}
          </div>

          {needed.includes('direction') && (
            <div>
              <label className={labelCls()}>Hướng</label>
              <select className={selectCls()} value={form.direction} onChange={(e) => set('direction', e.target.value as AlertDirection)}>
                {DIRECTION_OPTIONS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </div>
          )}

          {needed.includes('price') && (
            <div>
              <label className={labelCls()}>Mức giá (nghìn đồng)</label>
              <input type="number" className={inputCls(!!errors.price)} placeholder="VD: 80" value={form.price} onChange={(e) => set('price', e.target.value)} />
              {errors.price && <p className="mt-1 text-xs text-danger">{errors.price}</p>}
            </div>
          )}

          {needed.includes('changePct') && (
            <div>
              <label className={labelCls()}>% Biến động</label>
              <input type="number" className={inputCls(!!errors.changePct)} placeholder="VD: 5" value={form.changePct} onChange={(e) => set('changePct', e.target.value)} />
              {errors.changePct && <p className="mt-1 text-xs text-danger">{errors.changePct}</p>}
            </div>
          )}

          {needed.includes('threshold') && (
            <div>
              <label className={labelCls()}>Ngưỡng</label>
              <input type="number" className={inputCls(!!errors.threshold)} placeholder="VD: 70" value={form.threshold} onChange={(e) => set('threshold', e.target.value)} />
              {errors.threshold && <p className="mt-1 text-xs text-danger">{errors.threshold}</p>}
            </div>
          )}

          {needed.includes('period') && (
            <div>
              <label className={labelCls()}>Chu kỳ (nến)</label>
              <input type="number" className={inputCls()} value={form.period} onChange={(e) => set('period', e.target.value)} />
            </div>
          )}

          {needed.includes('multiplier') && (
            <div>
              <label className={labelCls()}>Hệ số nhân KL</label>
              <input type="number" className={inputCls()} placeholder="VD: 2" value={form.multiplier} onChange={(e) => set('multiplier', e.target.value)} />
            </div>
          )}

          {needed.includes('window') && (
            <div>
              <label className={labelCls()}>Cửa sổ tính TB (nến)</label>
              <input type="number" className={inputCls()} placeholder="VD: 20" value={form.window} onChange={(e) => set('window', e.target.value)} />
            </div>
          )}
        </div>

        {saveError && <p className="mt-3 text-sm text-danger">Lỗi: {saveError}</p>}

        <div className="mt-5 flex gap-2">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex h-9 min-w-[120px] items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Lưu quy tắc
          </button>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 items-center justify-center rounded-lg border border-border bg-card px-4 text-sm font-medium text-foreground hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {VI.common.cancel}
          </button>
        </div>
      </form>
    </Card>
  )
}

// ─── Hàng quy tắc ─────────────────────────────────────────────────────────────
function RuleRow({ rule, onRefresh }: { rule: AlertRuleItem; onRefresh: () => void }) {
  const [busy, setBusy] = useState(false)

  const sev = SEVERITY_MAP[rule.severity as AlertSeverity] ?? SEVERITY_MAP.info
  const dir = rule.parameters.direction ? (DIRECTION_MAP[rule.parameters.direction] ?? rule.parameters.direction) : null

  function paramSummary(): string {
    const p = rule.parameters
    const parts: string[] = []
    if (dir) parts.push(dir)
    if (p.price !== undefined) parts.push(`giá ${p.price}`)
    if (p.changePct !== undefined) parts.push(`${p.changePct}%`)
    if (p.threshold !== undefined) parts.push(`ngưỡng ${p.threshold}`)
    if (p.period !== undefined) parts.push(`chu kỳ ${p.period}`)
    if (p.multiplier !== undefined) parts.push(`×${p.multiplier}`)
    if (p.window !== undefined) parts.push(`cửa sổ ${p.window}`)
    return parts.join(', ')
  }

  async function toggle() {
    setBusy(true)
    try {
      if (rule.enabled) await alertsApi.disableRule(rule.id)
      else await alertsApi.enableRule(rule.id)
      onRefresh()
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!window.confirm('Xác nhận xoá quy tắc này?')) return
    setBusy(true)
    try {
      await alertsApi.deleteRule(rule.id)
      onRefresh()
    } finally {
      setBusy(false)
    }
  }

  return (
    <tr className="border-b border-border transition-colors hover:bg-secondary/30">
      <td className="px-3 py-3 font-mono text-sm font-semibold text-foreground">{rule.target}</td>
      <td className="px-3 py-3 text-sm text-foreground">{rule.name || '—'}</td>
      <td className="px-3 py-3">
        <Badge className="bg-secondary text-foreground">{labelForType(rule.alertType as AlertType)}</Badge>
      </td>
      <td className="px-3 py-3 text-xs text-muted-foreground">{paramSummary() || '—'}</td>
      <td className="px-3 py-3">
        <Badge className={sev.cls}>{sev.label}</Badge>
      </td>
      <td className="px-3 py-3">
        <span
          className={cn('inline-flex h-5 w-9 items-center rounded-full transition-colors', rule.enabled ? 'bg-up' : 'bg-secondary')}
          aria-label={rule.enabled ? 'Đang bật' : 'Đang tắt'}
        >
          <span className={cn('h-3.5 w-3.5 rounded-full bg-white shadow transition-transform', rule.enabled ? 'translate-x-4' : 'translate-x-1')} />
        </span>
      </td>
      <td className="px-3 py-3 text-xs text-muted-foreground">
        {rule.lastTriggeredAt
          ? new Date(rule.lastTriggeredAt).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
          : '—'}
      </td>
      <td className="px-3 py-3">
        <div className="flex items-center gap-0.5">
          <IconBtn onClick={toggle} title={rule.enabled ? 'Tắt quy tắc' : 'Bật quy tắc'} disabled={busy}>
            {rule.enabled ? <BellOff className="h-4 w-4" /> : <Bell className="h-4 w-4" />}
          </IconBtn>
          <IconBtn onClick={remove} title="Xoá quy tắc" disabled={busy} variant="danger">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
          </IconBtn>
        </div>
      </td>
    </tr>
  )
}

// ─── Hàng lịch sử kích hoạt ────────────────────────────────────────────────────
function TriggerRow({ item }: { item: AlertTriggerItem }) {
  const badge = triggerBadge(item.status)
  const [expanded, setExpanded] = useState(false)
  const hasReason = !!item.reason

  return (
    <>
      <tr className="border-b border-border transition-colors hover:bg-secondary/30">
        <td className="px-3 py-3 font-mono text-sm font-semibold text-foreground">{item.target}</td>
        <td className="px-3 py-3 text-xs text-muted-foreground">
          {item.triggeredAt
            ? new Date(item.triggeredAt).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
            : '—'}
        </td>
        <td className="px-3 py-3">
          <Badge className={badge.cls}>
            {badge.icon}
            {badge.label}
          </Badge>
        </td>
        <td className="px-3 py-3 font-mono text-sm text-foreground">
          {item.observedValue !== null && item.observedValue !== undefined ? String(item.observedValue) : '—'}
        </td>
        <td className="px-3 py-3 font-mono text-sm text-muted-foreground">
          {item.threshold !== null && item.threshold !== undefined ? String(item.threshold) : '—'}
        </td>
        <td className="px-3 py-3">
          {hasReason && (
            <button
              type="button"
              aria-label={expanded ? 'Thu gọn' : 'Xem lý do'}
              onClick={() => setExpanded((v) => !v)}
              className="flex h-7 w-7 items-center justify-center rounded text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          )}
        </td>
      </tr>
      {expanded && hasReason && (
        <tr className="border-b border-border bg-secondary/20">
          <td colSpan={6} className="px-4 py-2 text-xs text-muted-foreground">{item.reason}</td>
        </tr>
      )}
    </>
  )
}

// ─── Trang chính ──────────────────────────────────────────────────────────────
export default function CanhBaoPage() {
  const [showForm, setShowForm] = useState(false)

  // Quy tắc
  const [rules, setRules] = useState<AlertRuleItem[]>([])
  const [rulesTotal, setRulesTotal] = useState(0)
  const [rulesLoading, setRulesLoading] = useState(true)
  const [rulesError, setRulesError] = useState<string | null>(null)

  // Lịch sử
  const [triggers, setTriggers] = useState<AlertTriggerItem[]>([])
  const [triggersTotal, setTriggersTotal] = useState(0)
  const [triggersLoading, setTriggersLoading] = useState(true)
  const [triggersError, setTriggersError] = useState<string | null>(null)

  const loadRules = useCallback(async () => {
    setRulesLoading(true)
    setRulesError(null)
    try {
      const res = await alertsApi.listRules({ pageSize: 50 })
      setRules(res.items)
      setRulesTotal(res.total)
    } catch {
      setRulesError('Không thể tải quy tắc. Vui lòng thử lại.')
    } finally {
      setRulesLoading(false)
    }
  }, [])

  const loadTriggers = useCallback(async () => {
    setTriggersLoading(true)
    setTriggersError(null)
    try {
      const res = await alertsApi.listTriggers({ pageSize: 30 })
      setTriggers(res.items)
      setTriggersTotal(res.total)
    } catch {
      setTriggersError('Không thể tải lịch sử. Vui lòng thử lại.')
    } finally {
      setTriggersLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadRules()
    void loadTriggers()
  }, [loadRules, loadTriggers])

  function refreshAll() {
    void loadRules()
    void loadTriggers()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={VI.alerts.title}
        subtitle="Tự động nhận thông báo khi cổ phiếu đạt điều kiện kỹ thuật"
        actions={
          <div className="flex gap-2">
            <button
              type="button"
              onClick={refreshAll}
              aria-label="Làm mới"
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setShowForm((v) => !v)}
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Plus className="h-4 w-4" />
              {VI.alerts.addRule}
            </button>
          </div>
        }
      />

      {showForm && (
        <AddRuleForm
          onClose={() => setShowForm(false)}
          onSuccess={() => { setShowForm(false); void loadRules() }}
        />
      )}

      {/* Danh sách quy tắc */}
      <Card>
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <CardLabel icon={<Bell className="h-3.5 w-3.5" />}>{VI.alerts.rules}</CardLabel>
          <span className="text-xs text-muted-foreground">
            {rulesLoading
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : `${rulesTotal} quy tắc`}
          </span>
        </div>

        {rulesError ? (
          <div className="flex items-center gap-2 px-5 py-8 text-sm text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {rulesError}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2">Mã</th>
                  <th className="px-3 py-2">Tên</th>
                  <th className="px-3 py-2">Loại</th>
                  <th className="px-3 py-2">Tham số</th>
                  <th className="px-3 py-2">Mức độ</th>
                  <th className="px-3 py-2">Trạng thái</th>
                  <th className="px-3 py-2">Kích hoạt lần cuối</th>
                  <th className="px-3 py-2">Hành động</th>
                </tr>
              </thead>
              <tbody>
                {rulesLoading
                  ? Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} cols={8} />)
                  : rules.length === 0
                    ? (
                      <tr>
                        <td colSpan={8} className="px-5 py-10 text-center text-sm text-muted-foreground">
                          {VI.alerts.emptyState}
                        </td>
                      </tr>
                    )
                    : rules.map((r) => <RuleRow key={r.id} rule={r} onRefresh={loadRules} />)}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Lịch sử kích hoạt */}
      <Card>
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <CardLabel icon={<Clock className="h-3.5 w-3.5" />}>{VI.alerts.triggers}</CardLabel>
          <span className="text-xs text-muted-foreground">
            {triggersLoading
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : `${triggersTotal} lượt`}
          </span>
        </div>

        {triggersError ? (
          <div className="flex items-center gap-2 px-5 py-8 text-sm text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {triggersError}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2">Mã</th>
                  <th className="px-3 py-2">Thời điểm</th>
                  <th className="px-3 py-2">Kết quả</th>
                  <th className="px-3 py-2 font-mono">Giá trị</th>
                  <th className="px-3 py-2 font-mono">Ngưỡng</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {triggersLoading
                  ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={6} />)
                  : triggers.length === 0
                    ? (
                      <tr>
                        <td colSpan={6} className="px-5 py-10 text-center text-sm text-muted-foreground">
                          {VI.common.noData}
                        </td>
                      </tr>
                    )
                    : triggers.map((t) => <TriggerRow key={t.id} item={t} />)}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
