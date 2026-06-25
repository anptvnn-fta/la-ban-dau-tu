import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  Loader2,
  RefreshCw,
  Save,
  Settings,
} from 'lucide-react'
import { toast } from 'sonner'
import { Card } from '@/components/ui/card'
import { PageHeader } from '@/components/common/PageHeader'
import { cn } from '@/lib/utils'
import { systemConfigApi, SystemConfigConflictError, SystemConfigValidationError } from '@/api/systemConfig'
import type {
  SystemConfigCategory,
  SystemConfigFieldSchema,
  SystemConfigItem,
  SystemConfigResponse,
} from '@/types/systemConfig'
import { VI } from '@/strings/vi'

// ---------------------------------------------------------------------------
// Hằng số — lọc khóa thị trường Trung Quốc
// ---------------------------------------------------------------------------

const CHINA_KEY_FRAGMENTS = [
  'TUSHARE', 'AKSHARE', 'BAOSTOCK', 'PYTDX', 'EFINANCE',
  'TENCENT', 'TICKFLOW', 'FEISHU', 'WECHAT', 'DINGTALK',
  'PUSHPLUS', 'SERVERCHAN',
]

function isChinaKey(key: string): boolean {
  const upper = key.toUpperCase()
  return CHINA_KEY_FRAGMENTS.some((f) => upper.includes(f))
}

// ---------------------------------------------------------------------------
// Nhãn tiếng Việt cho danh mục
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  base: 'Cơ bản',
  data_source: 'Nguồn dữ liệu',
  ai_model: 'LLM / AI',
  notification: 'Thông báo',
  system: 'Hệ thống',
  agent: 'Tác nhân AI',
  backtest: 'Đánh giá dự báo',
  uncategorized: 'Khác',
}

function categoryLabel(cat: string): string {
  return CATEGORY_LABELS[cat] ?? cat
}

// ---------------------------------------------------------------------------
// Thứ tự hiển thị danh mục
// ---------------------------------------------------------------------------

const CATEGORY_ORDER: (SystemConfigCategory | string)[] = [
  'base', 'ai_model', 'data_source', 'notification', 'agent', 'backtest', 'system', 'uncategorized',
]

// ---------------------------------------------------------------------------
// Kiểu nội bộ
// ---------------------------------------------------------------------------

interface ConfigEntry {
  item: SystemConfigItem
  schema?: SystemConfigFieldSchema
  draft: string
  original: string
}

type GroupMap = Map<string, ConfigEntry[]>

// ---------------------------------------------------------------------------
// Hàm tiện ích
// ---------------------------------------------------------------------------

function buildGroups(data: SystemConfigResponse): GroupMap {
  const map: GroupMap = new Map()
  for (const item of data.items) {
    if (isChinaKey(item.key)) continue
    const cat = item.schema?.category ?? 'uncategorized'
    const val = item.value ?? ''
    const entry: ConfigEntry = { item, schema: item.schema, draft: val, original: val }
    if (!map.has(cat)) map.set(cat, [])
    map.get(cat)!.push(entry)
  }
  for (const entries of map.values()) {
    entries.sort((a, b) => (a.schema?.displayOrder ?? 999) - (b.schema?.displayOrder ?? 999))
  }
  return map
}

// ---------------------------------------------------------------------------
// PasswordInput — ô nhập mật khẩu có nút hiện/ẩn
// ---------------------------------------------------------------------------

function PasswordInput({
  id,
  value,
  onChange,
  disabled,
}: {
  id: string
  value: string
  onChange: (v: string) => void
  disabled?: boolean
}) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <input
        id={id}
        type={show ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="h-9 w-full rounded-lg border border-border bg-background pr-10 pl-3 text-sm font-mono text-foreground placeholder-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        autoComplete="new-password"
        spellCheck={false}
      />
      <button
        type="button"
        aria-label={show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
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
// ConfigControl — render đúng control theo uiControl / data_type
// ---------------------------------------------------------------------------

const baseInputClass =
  'h-9 w-full rounded-lg border border-border bg-background px-3 text-sm font-mono text-foreground placeholder-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50'

function ConfigControl({
  entry,
  onChange,
  disabled,
  error,
}: {
  entry: ConfigEntry
  onChange: (key: string, value: string) => void
  disabled?: boolean
  error?: string
}) {
  const { item, schema, draft } = entry
  const id = `cfg-${item.key}`
  const uiControl = schema?.uiControl ?? 'text'
  const isEditable = schema?.isEditable !== false
  const isSensitive = schema?.isSensitive ?? false
  const options = schema?.options ?? []
  const label = schema?.title ?? item.key
  const description = schema?.description

  return (
    <div className="flex flex-col gap-1.5">
      {/* Nhãn */}
      <label htmlFor={id} className="text-sm font-medium text-foreground leading-none">
        {label}
        {schema?.isRequired && (
          <span className="ml-1 text-danger" aria-label="bắt buộc">*</span>
        )}
      </label>

      {/* Mô tả */}
      {description && (
        <p className="text-xs text-muted-foreground leading-snug">{description}</p>
      )}

      {/* Điều khiển */}
      {uiControl === 'switch' ? (
        <label className="flex h-9 w-fit cursor-pointer items-center gap-3">
          <div className="relative inline-block">
            <input
              id={id}
              type="checkbox"
              checked={draft === 'true' || draft === '1'}
              onChange={(e) => onChange(item.key, e.target.checked ? 'true' : 'false')}
              disabled={disabled || !isEditable}
              className="peer sr-only"
            />
            {/* Track */}
            <div className="h-5 w-9 rounded-full bg-border transition-colors peer-checked:bg-primary peer-disabled:opacity-50" />
            {/* Thumb */}
            <div className="pointer-events-none absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform peer-checked:translate-x-4" />
          </div>
          <span className="text-sm text-foreground select-none">
            {(draft === 'true' || draft === '1') ? 'Bật' : 'Tắt'}
          </span>
        </label>
      ) : uiControl === 'select' ? (
        <select
          id={id}
          value={draft}
          onChange={(e) => onChange(item.key, e.target.value)}
          disabled={disabled || !isEditable}
          className={cn(baseInputClass, 'cursor-pointer')}
        >
          <option value="">-- Chọn --</option>
          {options.map((opt) => {
            const val = typeof opt === 'string' ? opt : opt.value
            const lbl = typeof opt === 'string' ? opt : opt.label
            return (
              <option key={val} value={val}>
                {lbl}
              </option>
            )
          })}
        </select>
      ) : (uiControl === 'password' || isSensitive) ? (
        <PasswordInput
          id={id}
          value={draft}
          onChange={(v) => onChange(item.key, v)}
          disabled={disabled || !isEditable}
        />
      ) : uiControl === 'textarea' ? (
        <textarea
          id={id}
          value={draft}
          onChange={(e) => onChange(item.key, e.target.value)}
          disabled={disabled || !isEditable}
          rows={3}
          spellCheck={false}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono text-foreground placeholder-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 resize-y"
        />
      ) : uiControl === 'number' ? (
        <input
          id={id}
          type="number"
          value={draft}
          onChange={(e) => onChange(item.key, e.target.value)}
          disabled={disabled || !isEditable}
          className={baseInputClass}
        />
      ) : (
        /* text / time / fallback */
        <input
          id={id}
          type="text"
          value={draft}
          onChange={(e) => onChange(item.key, e.target.value)}
          disabled={disabled || !isEditable}
          spellCheck={false}
          autoComplete="off"
          className={baseInputClass}
        />
      )}

      {/* Thông báo lỗi validate */}
      {error && (
        <p className="flex items-center gap-1 text-xs text-danger">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {error}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// CategorySection — nhóm có thể thu gọn
// ---------------------------------------------------------------------------

function CategorySection({
  category,
  entries,
  onChange,
  disabled,
  errors,
  defaultOpen,
}: {
  category: string
  entries: ConfigEntry[]
  onChange: (key: string, value: string) => void
  disabled?: boolean
  errors: Record<string, string>
  defaultOpen: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  const title = categoryLabel(category)
  const changedCount = entries.filter((e) => e.draft !== e.original).length
  const errorCount = entries.filter((e) => !!errors[e.item.key]).length

  return (
    <Card>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={`section-${category}`}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-2xl px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-heading text-base font-semibold text-foreground">{title}</span>
          {changedCount > 0 && (
            <span className="rounded-full bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary">
              {changedCount} thay đổi
            </span>
          )}
          {errorCount > 0 && (
            <span className="rounded-full bg-danger/15 px-2 py-0.5 text-xs font-medium text-danger">
              {errorCount} lỗi
            </span>
          )}
        </div>
        {open
          ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        }
      </button>

      {open && (
        <div
          id={`section-${category}`}
          className="grid grid-cols-1 gap-5 border-t border-border px-5 pb-6 pt-5 md:grid-cols-2"
        >
          {entries.map((entry) => (
            <ConfigControl
              key={entry.item.key}
              entry={entry}
              onChange={onChange}
              disabled={disabled}
              error={errors[entry.item.key]}
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
      {[4, 3, 4].map((count, i) => (
        // eslint-disable-next-line react/no-array-index-key
        <Card key={i} className="px-5 py-4">
          <div className="mb-5 h-5 w-36 animate-pulse rounded bg-secondary" />
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {Array.from({ length: count }).map((_, j) => (
              // eslint-disable-next-line react/no-array-index-key
              <div key={j} className="flex flex-col gap-2">
                <div className="h-3.5 w-32 animate-pulse rounded bg-secondary" />
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
// Trang chính: CaiDatPage
// ---------------------------------------------------------------------------

export default function CaiDatPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [groups, setGroups] = useState<GroupMap>(new Map())
  const [configVersion, setConfigVersion] = useState('')
  const [maskToken, setMaskToken] = useState('******')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [savedAt, setSavedAt] = useState<string | null>(null)

  // Ref để handler lưu luôn đọc được groups mới nhất
  const groupsRef = useRef<GroupMap>(groups)
  groupsRef.current = groups

  const loadConfig = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const data: SystemConfigResponse = await systemConfigApi.getConfig(true)
      setConfigVersion(data.configVersion)
      setMaskToken(data.maskToken ?? '******')
      setGroups(buildGroups(data))
      setFieldErrors({})
    } catch {
      setLoadError('Không thể tải cấu hình. Hãy kiểm tra kết nối máy chủ và thử lại.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConfig()
  }, [loadConfig])

  const handleChange = useCallback((key: string, value: string) => {
    setGroups((prev) => {
      const next = new Map(prev)
      for (const [cat, entries] of next) {
        const idx = entries.findIndex((e) => e.item.key === key)
        if (idx !== -1) {
          const updated = [...entries]
          updated[idx] = { ...updated[idx], draft: value }
          next.set(cat, updated)
          break
        }
      }
      return next
    })
    setFieldErrors((prev) => {
      if (!prev[key]) return prev
      const next = { ...prev }
      delete next[key]
      return next
    })
  }, [])

  const handleSave = async () => {
    const changedItems: { key: string; value: string }[] = []
    for (const entries of groupsRef.current.values()) {
      for (const e of entries) {
        if (e.draft !== e.original) {
          changedItems.push({ key: e.item.key, value: e.draft })
        }
      }
    }

    if (changedItems.length === 0) {
      toast.info('Không có thay đổi nào để lưu.')
      return
    }

    setSaving(true)
    setFieldErrors({})
    try {
      await systemConfigApi.update({
        configVersion,
        maskToken,
        reloadNow: true,
        items: changedItems,
      })

      // Sau khi lưu thành công: cập nhật original = draft
      setGroups((prev) => {
        const next = new Map(prev)
        for (const [cat, entries] of next) {
          next.set(cat, entries.map((e) => ({ ...e, original: e.draft })))
        }
        return next
      })

      const now = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
      setSavedAt(now)
      toast.success(`${VI.settings.saved} lúc ${now}`)
    } catch (err) {
      if (err instanceof SystemConfigConflictError) {
        toast.error('Xung đột phiên bản, hãy tải lại trang để lấy cấu hình mới nhất.')
        return
      }
      if (err instanceof SystemConfigValidationError) {
        const errMap: Record<string, string> = {}
        for (const issue of err.issues ?? []) {
          errMap[issue.key] = issue.message
        }
        setFieldErrors(errMap)
        toast.error('Một số trường không hợp lệ, hãy kiểm tra lại.')
        return
      }
      toast.error('Lưu cấu hình thất bại. Hãy thử lại.')
    } finally {
      setSaving(false)
    }
  }

  // Tổng số thay đổi chưa lưu
  const totalChanged = [...groups.values()].reduce(
    (sum, entries) => sum + entries.filter((e) => e.draft !== e.original).length,
    0,
  )

  // Sắp xếp danh sách category theo thứ tự ưu tiên
  const sortedCategories = [...groups.keys()].sort((a, b) => {
    const ia = CATEGORY_ORDER.indexOf(a)
    const ib = CATEGORY_ORDER.indexOf(b)
    if (ia === -1 && ib === -1) return a.localeCompare(b)
    if (ia === -1) return 1
    if (ib === -1) return -1
    return ia - ib
  })

  return (
    <>
      <PageHeader
        title={VI.settings.title}
        subtitle="Quản lý cấu hình hệ thống phân tích cổ phiếu Việt Nam"
        actions={
          <div className="flex items-center gap-2">
            {savedAt && !saving && (
              <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
                <CheckCircle2 className="h-3.5 w-3.5 text-up" />
                Đã lưu {savedAt}
              </span>
            )}

            <button
              type="button"
              aria-label="Tải lại cấu hình"
              onClick={loadConfig}
              disabled={loading || saving}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            </button>

            <button
              type="button"
              onClick={handleSave}
              disabled={loading || saving || totalChanged === 0}
              className="inline-flex min-h-[44px] min-w-[44px] items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              {saving
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <Save className="h-4 w-4" />
              }
              <span>
                {saving
                  ? 'Đang lưu…'
                  : totalChanged > 0
                    ? `${VI.settings.save} (${totalChanged})`
                    : VI.settings.save
                }
              </span>
            </button>
          </div>
        }
      />

      {/* Thông báo lỗi tải */}
      {loadError && !loading && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span className="flex-1">{loadError}</span>
          <button
            type="button"
            onClick={loadConfig}
            className="flex items-center gap-1 font-medium underline underline-offset-2 hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Thử lại
          </button>
        </div>
      )}

      {/* Skeleton khi đang tải */}
      {loading && <LoadingSkeleton />}

      {/* Danh sách nhóm cấu hình */}
      {!loading && !loadError && groups.size > 0 && (
        <div className="space-y-4">
          {sortedCategories.map((cat, idx) => (
            <CategorySection
              key={cat}
              category={cat}
              entries={groups.get(cat)!}
              onChange={handleChange}
              disabled={saving}
              errors={fieldErrors}
              defaultOpen={idx === 0}
            />
          ))}

          {/* Thông tin phiên bản */}
          <div className="flex items-center gap-2 px-1 text-xs text-muted-foreground">
            <Settings className="h-3.5 w-3.5 shrink-0" />
            <span>
              Phiên bản cấu hình:{' '}
              <code className="font-mono">{configVersion}</code>
            </span>
          </div>
        </div>
      )}

      {/* Trống */}
      {!loading && !loadError && groups.size === 0 && (
        <Card className="flex h-48 flex-col items-center justify-center gap-3 text-center">
          <Settings className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{VI.common.noData}</p>
        </Card>
      )}
    </>
  )
}
