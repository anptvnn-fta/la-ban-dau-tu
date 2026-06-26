import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Eye, EyeOff,
  Loader2, Play, RefreshCw, Save, Send, Settings, SlidersHorizontal,
} from 'lucide-react'
import { toast } from 'sonner'
import { Card } from '@/components/ui/card'
import { PageHeader } from '@/components/common/PageHeader'
import { cn } from '@/lib/utils'
import {
  systemConfigApi, SystemConfigConflictError, SystemConfigValidationError,
} from '@/api/systemConfig'
import type { SystemConfigFieldSchema, SchedulerStatusResponse } from '@/types/systemConfig'
import {
  SETTINGS_SECTIONS, SETTINGS_KEYS,
  type SettingField, type SettingGroup, type SettingSection, type SettingControl,
} from '@/config/settingsModel'
import { VI } from '@/strings/vi'

// ---------------------------------------------------------------------------
// Lớp dữ liệu nội bộ
// ---------------------------------------------------------------------------

interface ConfigState {
  values: Record<string, string>     // bản nháp đang sửa
  original: Record<string, string>   // giá trị gốc từ máy chủ
  schemas: Record<string, SystemConfigFieldSchema | undefined>
}

// Khóa đã được các đề mục "thân thiện" ở trên phụ trách → không lặp lại ở phần nâng cao.
const CURATED_KEYS = new Set(SETTINGS_KEYS)

// Cấu hình chỉ dành cho thị trường Trung Quốc / nguồn không dùng ở VN → vẫn ẩn.
const IRRELEVANT_FRAGMENTS = [
  'TUSHARE', 'AKSHARE', 'BAOSTOCK', 'PYTDX', 'EFINANCE', 'TENCENT', 'TICKFLOW',
  'FEISHU', 'WECHAT', 'DINGTALK', 'PUSHPLUS', 'SERVERCHAN', 'ANSPIRE', 'AIHUBMIX',
  'ALPHASIFT', 'LONGBRIDGE',
]
function isIrrelevantKey(key: string): boolean {
  const u = key.toUpperCase()
  return IRRELEVANT_FRAGMENTS.some((f) => u.includes(f))
}

// Nhãn + thứ tự danh mục cho phần "Cấu hình nâng cao".
const CAT_LABELS: Record<string, string> = {
  base: 'Cơ bản',
  ai_model: 'AI & Mô hình',
  data_source: 'Nguồn dữ liệu',
  notification: 'Thông báo & Báo cáo',
  agent: 'Trợ lý AI (Agent)',
  backtest: 'Đánh giá dự báo',
  system: 'Hệ thống',
  uncategorized: 'Khác',
}
const CAT_ORDER = ['base', 'ai_model', 'data_source', 'notification', 'agent', 'backtest', 'system', 'uncategorized']

const baseInputClass =
  'h-9 w-full rounded-lg border border-border bg-background px-3 text-sm font-mono text-foreground placeholder-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50'

function resolveControl(field: SettingField, schema?: SystemConfigFieldSchema): SettingControl {
  if (field.control) return field.control
  const ui = schema?.uiControl
  if (ui === 'switch' || ui === 'select' || ui === 'number' || ui === 'textarea' || ui === 'password') return ui
  if (schema?.isSensitive) return 'password'
  return 'text'
}

// ---------------------------------------------------------------------------
// Ô nhập mật khẩu (hiện/ẩn)
// ---------------------------------------------------------------------------

function PasswordInput({
  id, value, onChange, placeholder, disabled,
}: {
  id: string; value: string; onChange: (v: string) => void; placeholder?: string; disabled?: boolean
}) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <input
        id={id}
        type={show ? 'text' : 'password'}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={cn(baseInputClass, 'pr-10')}
        autoComplete="new-password"
        spellCheck={false}
      />
      <button
        type="button"
        aria-label={show ? 'Ẩn' : 'Hiện'}
        onClick={() => setShow((s) => !s)}
        disabled={disabled}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none"
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Một trường cấu hình
// ---------------------------------------------------------------------------

function FieldControl({
  field, value, schema, onChange, disabled, error,
}: {
  field: SettingField
  value: string
  schema?: SystemConfigFieldSchema
  onChange: (key: string, value: string) => void
  disabled?: boolean
  error?: string
}) {
  const id = `cfg-${field.key}`
  const control = resolveControl(field, schema)
  const options = field.options ?? (schema?.options ?? []).map((o) =>
    typeof o === 'string' ? { label: o, value: o } : o,
  )
  const isSwitch = control === 'switch'
  const locked = disabled || schema?.isEditable === false

  return (
    <div className={cn('flex flex-col gap-1.5', control === 'textarea' && 'sm:col-span-2')}>
      <label htmlFor={id} className="text-sm font-medium leading-none text-foreground">
        {field.label}
        {field.required && <span className="ml-1 text-danger" aria-label={VI.settings.required}>*</span>}
      </label>
      {field.help && <p className="text-xs leading-snug text-muted-foreground">{field.help}</p>}

      {isSwitch ? (
        <label className="flex h-9 w-fit cursor-pointer items-center gap-3">
          <div className="relative inline-block">
            <input
              id={id}
              type="checkbox"
              checked={value === 'true' || value === '1'}
              onChange={(e) => onChange(field.key, e.target.checked ? 'true' : 'false')}
              disabled={locked}
              className="peer sr-only"
            />
            <div className="h-5 w-9 rounded-full bg-border transition-colors peer-checked:bg-primary peer-disabled:opacity-50" />
            <div className="pointer-events-none absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform peer-checked:translate-x-4" />
          </div>
          <span className="select-none text-sm text-foreground">
            {(value === 'true' || value === '1') ? 'Bật' : 'Tắt'}
          </span>
        </label>
      ) : control === 'select' ? (
        <select
          id={id}
          value={value}
          onChange={(e) => onChange(field.key, e.target.value)}
          disabled={locked}
          className={cn(baseInputClass, 'cursor-pointer')}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      ) : control === 'password' ? (
        <PasswordInput id={id} value={value} placeholder={field.placeholder} onChange={(v) => onChange(field.key, v)} disabled={locked} />
      ) : control === 'textarea' ? (
        <textarea
          id={id}
          value={value}
          placeholder={field.placeholder}
          onChange={(e) => onChange(field.key, e.target.value)}
          disabled={locked}
          rows={2}
          spellCheck={false}
          className="w-full resize-y rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono text-foreground placeholder-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        />
      ) : (
        <input
          id={id}
          type={control === 'number' ? 'number' : control === 'time' ? 'time' : 'text'}
          value={value}
          placeholder={field.placeholder}
          onChange={(e) => onChange(field.key, e.target.value)}
          disabled={locked}
          spellCheck={false}
          autoComplete="off"
          className={baseInputClass}
        />
      )}

      {error && (
        <p className="flex items-center gap-1 text-xs text-danger">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />{error}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Nút "Gửi thử" cho Telegram/Email
// ---------------------------------------------------------------------------

function TestNotifyButton({
  channel, keys, state, maskToken,
}: {
  channel: 'telegram' | 'email'
  keys: string[]
  state: ConfigState
  maskToken: string
}) {
  const [busy, setBusy] = useState(false)
  const run = async () => {
    const hasValue = keys.some((k) => (state.values[k] ?? '').trim() !== '')
    if (!hasValue) {
      toast.info(VI.settings.testMissing)
      return
    }
    setBusy(true)
    try {
      const items = keys.map((k) => ({ key: k, value: state.values[k] ?? '' }))
      const res = await systemConfigApi.testNotificationChannel({ channel, items, maskToken })
      if (res?.success) toast.success(VI.settings.testOk)
      else toast.error(res?.message || VI.settings.testFail)
    } catch {
      toast.error(VI.settings.testFail)
    } finally {
      setBusy(false)
    }
  }
  return (
    <button
      type="button"
      onClick={run}
      disabled={busy}
      className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-medium text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
      {busy ? VI.settings.testing : VI.settings.testSend}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Widget lịch: trạng thái + "Chạy ngay"
// ---------------------------------------------------------------------------

function SchedulerWidget() {
  const [status, setStatus] = useState<SchedulerStatusResponse | null>(null)
  const [busy, setBusy] = useState(false)

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await systemConfigApi.getSchedulerStatus())
    } catch {
      /* im lặng — không chặn trang nếu API lịch lỗi */
    }
  }, [])

  useEffect(() => { void loadStatus() }, [loadStatus])

  const runNow = async () => {
    setBusy(true)
    try {
      await systemConfigApi.runSchedulerNow()
      toast.success(VI.settings.ranNow)
      setTimeout(() => void loadStatus(), 1500)
    } catch {
      toast.error(VI.settings.runFailed)
    } finally {
      setBusy(false)
    }
  }

  const enabled = status?.enabled
  const fmt = (v?: string | null) => (v ? new Date(v).toLocaleString('vi-VN') : VI.settings.schedNever)

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-background/40 px-4 py-3">
      <div className="flex flex-col gap-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className={cn('h-2 w-2 rounded-full', enabled ? 'bg-up' : 'bg-muted-foreground/40')} />
          <span className="font-medium text-foreground">
            {enabled ? VI.settings.schedStatusOn : VI.settings.schedStatusOff}
          </span>
          {status?.running && <span className="text-up">· {VI.settings.schedRunning}</span>}
        </span>
        {status && (
          <span>{VI.settings.schedLastRun}: {fmt(status.lastRunAt)}</span>
        )}
      </div>
      <button
        type="button"
        onClick={runNow}
        disabled={busy}
        className="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        {busy ? VI.settings.running : VI.settings.runNow}
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Một nhóm trong đề mục
// ---------------------------------------------------------------------------

function GroupBlock({
  group, state, maskToken, onChange, disabled, errors,
}: {
  group: SettingGroup
  state: ConfigState
  maskToken: string
  onChange: (key: string, value: string) => void
  disabled?: boolean
  errors: Record<string, string>
}) {
  const [open, setOpen] = useState(!group.advanced)

  const body = (
    <>
      {group.intro && <p className="mb-3 text-xs leading-snug text-muted-foreground">{group.intro}</p>}
      <div className="grid grid-cols-1 gap-x-5 gap-y-4 sm:grid-cols-2">
        {group.fields.map((field) => (
          <FieldControl
            key={field.key}
            field={field}
            value={state.values[field.key] ?? ''}
            schema={state.schemas[field.key]}
            onChange={onChange}
            disabled={disabled}
            error={errors[field.key]}
          />
        ))}
      </div>
      {group.action === 'scheduler-run' && <div className="mt-4"><SchedulerWidget /></div>}
      {group.action === 'test-telegram' && (
        <div className="mt-3"><TestNotifyButton channel="telegram" keys={['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']} state={state} maskToken={maskToken} /></div>
      )}
      {group.action === 'test-email' && (
        <div className="mt-3"><TestNotifyButton channel="email" keys={['EMAIL_SENDER', 'EMAIL_PASSWORD', 'EMAIL_RECEIVERS']} state={state} maskToken={maskToken} /></div>
      )}
    </>
  )

  if (!group.advanced) {
    return (
      <div className="border-t border-border/70 px-5 py-4 first:border-t-0">
        <h4 className="mb-2 text-sm font-semibold text-foreground">{group.title}</h4>
        {body}
      </div>
    )
  }

  // Nhóm nâng cao → thu gọn được
  return (
    <div className="border-t border-border/70 px-5 py-3">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-1.5 text-left text-sm font-semibold text-muted-foreground hover:text-foreground focus-visible:outline-none"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        {group.title}
        <span className="text-xs font-normal text-muted-foreground/70">· {VI.settings.advanced.toLowerCase()}</span>
      </button>
      {open && <div className="mt-3">{body}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Một đề mục (Card)
// ---------------------------------------------------------------------------

function SectionCard({
  section, state, maskToken, onChange, disabled, errors,
}: {
  section: SettingSection
  state: ConfigState
  maskToken: string
  onChange: (key: string, value: string) => void
  disabled?: boolean
  errors: Record<string, string>
}) {
  // Mặc định thu gọn TẤT CẢ đề mục — gọn gàng, click vào header mới sổ ra.
  const [open, setOpen] = useState(false)
  const Icon = section.icon
  const changed = section.groups.some((g) => g.fields.some((f) => state.values[f.key] !== state.original[f.key]))
  const errCount = section.groups.reduce(
    (n, g) => n + g.fields.filter((f) => errors[f.key]).length, 0,
  )

  return (
    <Card>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-3 rounded-2xl px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/12 text-primary">
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-heading text-base font-semibold text-foreground">{section.title}</span>
            {changed && <span className="rounded-full bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary">●</span>}
            {errCount > 0 && <span className="rounded-full bg-danger/15 px-2 py-0.5 text-xs font-medium text-danger">{errCount} lỗi</span>}
          </div>
          <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{section.blurb}</p>
        </div>
        {open ? <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" /> : <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />}
      </button>

      {open && (
        <div className="border-t border-border">
          {section.groups.map((group) => (
            <GroupBlock
              key={group.id}
              group={group}
              state={state}
              maskToken={maskToken}
              onChange={onChange}
              disabled={disabled}
              errors={errors}
            />
          ))}
          {section.note === 'alert-rules' && (
            <div className="border-t border-border/70 px-5 py-3 text-xs text-muted-foreground">
              {VI.settings.alertRulesHint}{' '}
              <Link to="/canh-bao" className="font-medium text-primary hover:underline">{VI.settings.alertRulesLink}</Link>.
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Cấu hình nâng cao — gom mọi khóa còn lại theo danh mục (không cắt bớt)
// ---------------------------------------------------------------------------

type AdvItem = { key: string; schema?: SystemConfigFieldSchema }

function AdvancedCategoryBlock({
  cat, items, state, onChange, disabled, errors,
}: {
  cat: string
  items: AdvItem[]
  state: ConfigState
  onChange: (key: string, value: string) => void
  disabled?: boolean
  errors: Record<string, string>
}) {
  const [open, setOpen] = useState(false)
  const label = CAT_LABELS[cat] ?? cat
  const changed = items.some((it) => state.values[it.key] !== state.original[it.key])

  return (
    <div className="border-t border-border/70 px-5 py-3">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-1.5 text-left text-sm font-semibold text-foreground hover:text-primary focus-visible:outline-none"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        {label}
        <span className="text-xs font-normal text-muted-foreground/70">· {items.length} mục</span>
        {changed && <span className="ml-1 h-1.5 w-1.5 rounded-full bg-primary" />}
      </button>
      {open && (
        <div className="mt-3 grid grid-cols-1 gap-x-5 gap-y-4 sm:grid-cols-2">
          {items.map((it) => (
            <FieldControl
              key={it.key}
              field={{ key: it.key, label: it.schema?.title || it.key, help: it.schema?.description }}
              value={state.values[it.key] ?? ''}
              schema={it.schema}
              onChange={onChange}
              disabled={disabled}
              error={errors[it.key]}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function AdvancedSection({
  groups, state, onChange, disabled, errors,
}: {
  groups: [string, AdvItem[]][]
  state: ConfigState
  onChange: (key: string, value: string) => void
  disabled?: boolean
  errors: Record<string, string>
}) {
  const [open, setOpen] = useState(false)
  const total = groups.reduce((n, [, items]) => n + items.length, 0)
  if (!total) return null

  return (
    <Card>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-3 rounded-2xl px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-muted-foreground">
          <SlidersHorizontal className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <span className="font-heading text-base font-semibold text-foreground">Cấu hình nâng cao</span>
          <p className="mt-0.5 text-xs leading-snug text-muted-foreground">
            Toàn bộ {total} tùy chọn còn lại, gom theo nhóm. Dành cho người dùng rành kỹ thuật — để mặc định nếu bạn không chắc.
          </p>
        </div>
        {open ? <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" /> : <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />}
      </button>
      {open && (
        <div className="border-t border-border">
          {groups.map(([cat, items]) => (
            <AdvancedCategoryBlock
              key={cat}
              cat={cat}
              items={items}
              state={state}
              onChange={onChange}
              disabled={disabled}
              errors={errors}
            />
          ))}
        </div>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="px-5 py-4">
          <div className="mb-4 flex items-center gap-3">
            <div className="h-9 w-9 animate-pulse rounded-xl bg-secondary" />
            <div className="h-5 w-40 animate-pulse rounded bg-secondary" />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {[0, 1].map((j) => (
              <div key={j} className="flex flex-col gap-2">
                <div className="h-3.5 w-28 animate-pulse rounded bg-secondary" />
                <div className="h-9 w-full animate-pulse rounded-lg bg-secondary" />
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Trang chính
// ---------------------------------------------------------------------------

export default function CaiDatPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [state, setState] = useState<ConfigState>({ values: {}, original: {}, schemas: {} })
  const [configVersion, setConfigVersion] = useState('')
  const [maskToken, setMaskToken] = useState('******')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [savedAt, setSavedAt] = useState<string | null>(null)

  const stateRef = useRef(state)
  stateRef.current = state

  const loadConfig = useCallback(async () => {
    setLoading(true)
    setLoadError(false)
    try {
      const data = await systemConfigApi.getConfig(true)
      const values: Record<string, string> = {}
      const schemas: Record<string, SystemConfigFieldSchema | undefined> = {}
      for (const item of data.items) {
        // Tải TẤT CẢ khóa (kể cả phần nâng cao) — không cắt bớt; phần hiển thị
        // do mô hình curated + nhóm nâng cao quyết định.
        values[item.key] = item.value ?? ''
        schemas[item.key] = item.schema
      }
      setState({ values, original: { ...values }, schemas })
      setConfigVersion(data.configVersion)
      setMaskToken(data.maskToken ?? '******')
      setErrors({})
    } catch {
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void loadConfig() }, [loadConfig])

  const handleChange = useCallback((key: string, value: string) => {
    setState((prev) => ({ ...prev, values: { ...prev.values, [key]: value } }))
    setErrors((prev) => {
      if (!prev[key]) return prev
      const next = { ...prev }; delete next[key]; return next
    })
  }, [])

  const changedKeys = useMemo(
    () => Object.keys(state.original).filter((k) => state.values[k] !== state.original[k]),
    [state],
  )

  // Nhóm cấu hình nâng cao: mọi khóa chưa được đề mục thân thiện phụ trách, gom theo danh mục.
  const advancedGroups = useMemo(() => {
    const map = new Map<string, { key: string; schema?: SystemConfigFieldSchema }[]>()
    for (const key of Object.keys(state.schemas)) {
      if (CURATED_KEYS.has(key) || isIrrelevantKey(key)) continue
      const schema = state.schemas[key]
      const cat = schema?.category ?? 'uncategorized'
      if (!map.has(cat)) map.set(cat, [])
      map.get(cat)!.push({ key, schema })
    }
    for (const arr of map.values()) {
      arr.sort((a, b) => (a.schema?.displayOrder ?? 999) - (b.schema?.displayOrder ?? 999))
    }
    return [...map.entries()].sort((a, b) => {
      const ia = CAT_ORDER.indexOf(a[0]); const ib = CAT_ORDER.indexOf(b[0])
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })
  }, [state.schemas])

  const handleSave = async () => {
    const s = stateRef.current
    const items = Object.keys(s.original)
      .filter((k) => s.values[k] !== s.original[k])
      .map((k) => ({ key: k, value: s.values[k] ?? '' }))

    if (items.length === 0) {
      toast.info(VI.settings.noChanges)
      return
    }

    setSaving(true)
    setErrors({})
    try {
      await systemConfigApi.update({ configVersion, maskToken, reloadNow: true, items })
      setState((prev) => ({ ...prev, original: { ...prev.values } }))
      const now = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
      setSavedAt(now)
      toast.success(`${VI.settings.saved} ${now}`)
      void loadConfig()
    } catch (err) {
      if (err instanceof SystemConfigConflictError) {
        toast.error(VI.settings.conflict)
      } else if (err instanceof SystemConfigValidationError) {
        const map: Record<string, string> = {}
        for (const issue of err.issues ?? []) map[issue.key] = issue.message
        setErrors(map)
        toast.error(VI.settings.invalid)
      } else {
        toast.error(VI.settings.saveFailed)
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        title={VI.settings.title}
        subtitle={VI.settings.subtitle}
        actions={
          <div className="flex items-center gap-2">
            {savedAt && !saving && (
              <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
                <CheckCircle2 className="h-3.5 w-3.5 text-up" />{VI.settings.savedAt} {savedAt}
              </span>
            )}
            <button
              type="button"
              aria-label={VI.settings.reload}
              onClick={loadConfig}
              disabled={loading || saving}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={loading || saving || changedKeys.length === 0}
              className="inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              <span>
                {saving ? VI.settings.saving : changedKeys.length > 0 ? `${VI.settings.save} (${changedKeys.length})` : VI.settings.save}
              </span>
            </button>
          </div>
        }
      />

      {loadError && !loading && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span className="flex-1">{VI.settings.loadError}</span>
          <button type="button" onClick={loadConfig} className="flex items-center gap-1 font-medium underline underline-offset-2 hover:no-underline">
            <RefreshCw className="h-3.5 w-3.5" />{VI.common.retry}
          </button>
        </div>
      )}

      {loading && <LoadingSkeleton />}

      {!loading && !loadError && (
        <div className="space-y-4">
          {SETTINGS_SECTIONS.map((section) => (
            <SectionCard
              key={section.id}
              section={section}
              state={state}
              maskToken={maskToken}
              onChange={handleChange}
              disabled={saving}
              errors={errors}
            />
          ))}

          <AdvancedSection
            groups={advancedGroups}
            state={state}
            onChange={handleChange}
            disabled={saving}
            errors={errors}
          />

          <div className="flex flex-col gap-1.5 px-1 pt-1 text-xs text-muted-foreground">
            <span>{VI.settings.footerNote}</span>
            <span className="flex items-center gap-1.5">
              <Settings className="h-3.5 w-3.5 shrink-0" />
              {VI.settings.version}: <code className="font-mono">{configVersion}</code>
            </span>
          </div>
        </div>
      )}
    </>
  )
}
