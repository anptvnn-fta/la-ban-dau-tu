import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Compass, Sparkles, ShieldCheck, Info, AlertCircle, AlertTriangle, Loader2,
  ChevronRight, ChevronLeft, RefreshCw, PiggyBank, Landmark, LineChart, Coins, User,
} from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardLabel } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { fmtCompact } from '@/utils/num'
import { VI } from '@/strings/vi'
import { tuVanApi } from '@/api/tuvan'
import type {
  TuVanOptions, TuVanField, TuVanForm, TuVanResult, AiResult, StockBuckets,
} from '@/types/tuvan'

const css = (name: string, fallback: string) =>
  typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    : fallback

const inputCls =
  'h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50'

const ASSET_COLOR: Record<string, string> = {
  tiet_kiem: '#10b981', trai_phieu: '#8b5cf6', co_phieu: css('--primary', '#3b82f6'), vang: '#f59e0b',
}
const BUCKET_COLOR: Record<string, string> = {
  on_dinh: css('--up', '#22c55e'), trung_binh: '#f59e0b', rui_ro: css('--down', '#ef4444'),
}
const GROUP_TONE: Record<string, string> = {
  phong_thu: 'bg-up/10 text-up border-up/30',
  can_bang: 'bg-primary/10 text-primary border-primary/30',
  tan_cong: 'bg-down/10 text-down border-down/30',
}

// 3 bước của wizard, gom theo nhóm dữ liệu.
const STEPS: { title: string; subtitle: string; groups: string[] }[] = [
  { title: 'Về bạn', subtitle: 'Vài nét cơ bản giúp hiểu giai đoạn cuộc đời của bạn', groups: ['nhan_khau'] },
  { title: 'Tình hình tài chính', subtitle: 'Đánh giá khả năng chịu rủi ro thực tế — thông tin không lưu nhận dạng cá nhân', groups: ['tai_chinh', 'muc_tieu'] },
  { title: 'Mục tiêu & Phong cách', subtitle: 'Khẩu vị và hành vi đầu tư của bạn — không có câu trả lời đúng/sai', groups: ['rui_ro', 'hanh_vi'] },
]

const isEmpty = (v: unknown) =>
  v === undefined || v === '' || v === null || (Array.isArray(v) && v.length === 0)

// ─── Ô nhập một trường ───────────────────────────────────────────────────────

function FieldInput({ field, value, error, onChange }: {
  field: TuVanField
  value: string | number | string[] | undefined
  error?: boolean
  onChange: (v: string | number | string[]) => void
}) {
  const labelEl = (
    <label className="mb-1 block text-xs font-medium text-muted-foreground">
      {field.label}{field.required && <span className="text-down"> *</span>}
    </label>
  )

  if (field.type === 'number') {
    return (
      <div>
        {labelEl}
        <input
          type="number" min={field.min} max={field.max}
          value={(value as number) ?? ''}
          onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          placeholder={field.note ?? ''}
          className={cn(inputCls, 'font-mono', error && 'border-down ring-1 ring-down')}
        />
        {field.note && <p className="mt-1 text-[11px] text-muted-foreground">{field.note}</p>}
        {error && <p className="mt-1 text-xs text-down">Bắt buộc</p>}
      </div>
    )
  }

  if (field.multi) {
    const arr = (value as string[]) || []
    const toggle = (k: string) => onChange(arr.includes(k) ? arr.filter(x => x !== k) : [...arr, k])
    return (
      <div className="sm:col-span-2">
        {labelEl}
        <div className="flex flex-wrap gap-1.5">
          {field.options?.map(o => (
            <button
              key={o.key} type="button" onClick={() => toggle(o.key)}
              className={cn('rounded-lg border px-2.5 py-1 text-xs transition-colors',
                arr.includes(o.key)
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border bg-card text-muted-foreground hover:bg-secondary')}
            >
              {o.label}
            </button>
          ))}
        </div>
        {field.note && <p className="mt-1 text-[11px] text-muted-foreground">{field.note}</p>}
      </div>
    )
  }

  // select
  return (
    <div>
      {labelEl}
      <select
        value={(value as string) ?? ''}
        onChange={e => onChange(e.target.value)}
        className={cn(inputCls, 'cursor-pointer', error && 'border-down ring-1 ring-down')}
      >
        <option value="">— Chọn —</option>
        {field.options?.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
      </select>
      {field.note && <p className="mt-1 text-[11px] text-muted-foreground">{field.note}</p>}
      {error && <p className="mt-1 text-xs text-down">Bắt buộc</p>}
    </div>
  )
}

// ─── Khu kết quả ─────────────────────────────────────────────────────────────

function RiskGroupCard({ r }: { r: TuVanResult }) {
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted-foreground">Nhóm nhà đầu tư của bạn</p>
          <span className={cn('mt-1 inline-flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xl font-bold', GROUP_TONE[r.finalGroup])}>
            <ShieldCheck className="h-5 w-5" aria-hidden />{r.finalLabel}
          </span>
        </div>
        {r.forcedDefensive && (
          <span className="inline-flex items-center gap-1 rounded-full border border-up/30 bg-up/10 px-2.5 py-1 text-xs font-medium text-up">
            <Info className="h-3.5 w-3.5" aria-hidden />Bảo vệ vốn tối đa được áp dụng
          </span>
        )}
      </div>

      {/* 3 tầng: Khẩu vị | Khả năng | Kết quả */}
      <div className="mt-4 grid grid-cols-3 gap-2 text-center">
        {[
          { k: 'Khẩu vị', v: r.tolerance.label, hint: `${r.tolerance.total}/18 điểm` },
          { k: 'Khả năng tài chính', v: r.capacity.label, hint: `${r.capacity.score}/16 điểm` },
          { k: 'Kết quả áp dụng', v: r.finalLabel, hint: 'nguyên tắc thận trọng', strong: true },
        ].map((c, i) => (
          <div key={i} className={cn('rounded-lg border p-2.5', c.strong ? 'border-primary/40 bg-primary/5' : 'border-border/60')}>
            <p className="text-[11px] text-muted-foreground">{c.k}</p>
            <p className={cn('mt-0.5 text-sm font-bold', c.strong ? 'text-primary' : 'text-foreground')}>{c.v}</p>
            <p className="text-[10px] text-muted-foreground">{c.hint}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        Nhóm cuối lấy mức <span className="font-medium text-foreground">thấp hơn</span> giữa Khả năng và Khẩu vị — để bạn không chịu rủi ro vượt quá sức mình. {r.finalDesc}
      </p>
    </Card>
  )
}

function AiPortraitCard({ ai, loading, error }: { ai: AiResult | null; loading: boolean; error: boolean }) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <CardLabel icon={<User className="h-3.5 w-3.5" aria-hidden />}>Phân tích chân dung (AI)</CardLabel>
        <span className="text-[10px] text-muted-foreground">AI diễn giải — mang tính tham khảo</span>
      </div>
      {loading ? (
        <div className="mt-3 space-y-2">
          {[0, 1, 2].map(i => <div key={i} className="h-3 animate-pulse rounded bg-secondary" style={{ width: `${90 - i * 12}%` }} />)}
          <p className="pt-1 text-xs text-muted-foreground">Đang phân tích hồ sơ của bạn…</p>
        </div>
      ) : ai ? (
        <div className="mt-2 space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>{ai.sections.chanDung}</p>
          <p><span className="font-medium text-foreground">Vì sao nhóm này: </span>{ai.sections.lyDoNhom}</p>
        </div>
      ) : error ? (
        <p className="mt-3 flex items-center gap-1.5 text-sm text-muted-foreground"><AlertCircle className="h-4 w-4" aria-hidden />Không lấy được phân tích AI lúc này. Kết quả phân bổ bên dưới vẫn đầy đủ.</p>
      ) : null}
    </Card>
  )
}

function AllocationCard({ r }: { r: TuVanResult }) {
  const pie = r.allocation.map(a => ({ name: a.label, value: a.percent, key: a.assetClass }))
  return (
    <Card className="p-5">
      <CardLabel icon={<LineChart className="h-3.5 w-3.5" aria-hidden />}>Phân bổ danh mục đề xuất</CardLabel>
      <p className="mb-2 mt-1 text-xs text-muted-foreground">
        Tỷ trọng do hệ thống tính theo nhóm của bạn{r.timeTilt !== 'giu_nguyen' && r.years != null
          ? ` (đã nghiêng theo mục tiêu ${r.years} năm)` : ''}.{r.vonMidpointTrieu ? ` Số tiền ước tính theo khoảng vốn ~${r.vonMidpointTrieu} triệu.` : ''}
      </p>
      <div className="grid items-center gap-4 sm:grid-cols-2">
        <ResponsiveContainer width="100%" height={230}>
          <PieChart>
            <Pie data={pie} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={52} outerRadius={90} paddingAngle={2} label={({ value }) => `${value}%`}>
              {pie.map(d => <Cell key={d.key} fill={ASSET_COLOR[d.key]} stroke={css('--card', '#0f172a')} strokeWidth={2} />)}
            </Pie>
            <Tooltip
              contentStyle={{ background: css('--card', '#0f172a'), border: `1px solid ${css('--border', '#334155')}`, borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: css('--foreground', '#f8fafc') }}
              formatter={(value) => `${value}%`}
            />
            <Legend formatter={(v) => <span className="text-xs text-muted-foreground">{v}</span>} />
          </PieChart>
        </ResponsiveContainer>
        <div className="space-y-1.5">
          {r.allocation.map(a => (
            <div key={a.assetClass} className="flex items-center justify-between gap-2 rounded-lg border border-border/60 px-3 py-2">
              <span className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-sm" style={{ background: ASSET_COLOR[a.assetClass] }} aria-hidden />
                <span className="text-sm font-medium text-foreground">{a.label}</span>
              </span>
              <span className="text-right">
                <span className="font-mono text-sm font-bold tabular-nums text-foreground">{a.percent}%</span>
                {a.amountTrieu != null && <span className="ml-2 font-mono text-xs text-muted-foreground">≈ {a.amountTrieu} tr</span>}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

function ChannelCards({ r, stocks, stocksLoading, stocksError }: { r: TuVanResult; stocks: StockBuckets | null; stocksLoading: boolean; stocksError: boolean }) {
  const md = r.marketData
  const term = md?.tietKiem?.termMonths
  const splitByBucket = Object.fromEntries(r.stockSplit.map(s => [s.bucket, s]))
  const premiumHigh = (md?.vang?.premiumPct ?? 0) > 15

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {/* Tiết kiệm */}
      <Card className="p-4">
        <CardLabel icon={<PiggyBank className="h-3.5 w-3.5 text-emerald-500" aria-hidden />}>Tiết kiệm{term ? ` · kỳ hạn ${term} tháng` : ''}</CardLabel>
        {md?.tietKiem?.top?.length ? (
          <ul className="mt-2 space-y-1.5">
            {md.tietKiem.top.map(b => (
              <li key={b.bank} className="flex items-center justify-between text-sm">
                <span className="text-foreground">{b.bank}</span>
                <span className="font-mono font-semibold tabular-nums text-emerald-500">{b.rate}%/năm</span>
              </li>
            ))}
          </ul>
        ) : <p className="mt-2 text-xs text-muted-foreground">Chưa lấy được lãi suất lúc này.</p>}
      </Card>

      {/* Trái phiếu */}
      <Card className="p-4">
        <CardLabel icon={<Landmark className="h-3.5 w-3.5 text-violet-500" aria-hidden />}>Trái phiếu & lãi suất nền</CardLabel>
        {md?.traiPhieu ? (
          <ul className="mt-2 space-y-1.5 text-sm">
            <li className="flex justify-between"><span className="text-muted-foreground">Lãi suất điều hành SBV</span><span className="font-mono font-semibold text-foreground">{md.traiPhieu.sbvPolicyRate}%</span></li>
            <li className="flex justify-between"><span className="text-muted-foreground">Trái phiếu Mỹ 10 năm</span><span className="font-mono font-semibold text-foreground">{md.traiPhieu.usYield}%</span></li>
            <li className="flex justify-between"><span className="text-muted-foreground">TPCP VN 10 năm (tham khảo)</span><span className="font-mono font-semibold text-foreground">~{md.traiPhieu.vn10yRef}%</span></li>
          </ul>
        ) : <p className="mt-2 text-xs text-muted-foreground">Chưa lấy được dữ liệu trái phiếu.</p>}
      </Card>

      {/* Cổ phiếu — 3 rổ */}
      <Card className="p-4 lg:col-span-2">
        <CardLabel icon={<LineChart className="h-3.5 w-3.5 text-primary" aria-hidden />}>Cổ phiếu theo 3 rổ biến động</CardLabel>
        <div className="mt-2 grid gap-3 sm:grid-cols-3">
          {(['on_dinh', 'trung_binh', 'rui_ro'] as const).map(bk => {
            const split = splitByBucket[bk]
            const bucket = stocks?.buckets.find(b => b.bucket === bk)
            return (
              <div key={bk} className="rounded-xl border border-border/60 p-3">
                <div className="mb-1 flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                    <span className="h-2.5 w-2.5 rounded-sm" style={{ background: BUCKET_COLOR[bk] }} aria-hidden />{split?.label}
                  </span>
                  {split && <span className="font-mono text-xs text-muted-foreground">{split.portfolioPct}% danh mục</span>}
                </div>
                <p className="mb-2 text-[11px] text-muted-foreground">{split?.withinStockPct}% phần cổ phiếu</p>
                {stocksLoading ? (
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin" aria-hidden />Đang lấy mã…</div>
                ) : bucket?.stocks.length ? (
                  <ul className="space-y-1">
                    {bucket.stocks.slice(0, 5).map(s => (
                      <li key={s.symbol} className="flex items-center justify-between text-sm">
                        <span className="font-mono font-bold tracking-wide text-foreground">{s.symbol}</span>
                        <span className="font-mono text-xs tabular-nums text-muted-foreground">{s.volatilityPct}%</span>
                      </li>
                    ))}
                  </ul>
                ) : (stocksError || !stocks) ? (
                  <p className="text-xs italic text-muted-foreground">Chưa lấy được danh sách mã.</p>
                ) : <p className="text-xs italic text-muted-foreground">Chưa có mã phù hợp.</p>}
              </div>
            )
          })}
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">Biến động đo bằng biên độ giá 1 năm (252 phiên): (đỉnh − đáy)/đáy. Mã có thể đổi rổ theo thời gian.</p>
        {stocks?.dataWarning && <p className="mt-1 text-[11px] text-muted-foreground/80">{stocks.dataWarning}</p>}
      </Card>

      {/* Vàng */}
      <Card className="p-4 lg:col-span-2">
        <CardLabel icon={<Coins className="h-3.5 w-3.5 text-amber-500" aria-hidden />}>Vàng</CardLabel>
        {md?.vang ? (
          <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
            <span><span className="text-muted-foreground">SJC mua: </span><span className="font-mono font-semibold text-foreground">{fmtCompact(md.vang.sjcBuy ?? 0)}</span></span>
            <span><span className="text-muted-foreground">SJC bán: </span><span className="font-mono font-semibold text-foreground">{fmtCompact(md.vang.sjcSell ?? 0)}</span></span>
            <span><span className="text-muted-foreground">Chênh lệch thế giới: </span><span className={cn('font-mono font-semibold', premiumHigh ? 'text-amber-500' : 'text-foreground')}>{md.vang.premiumPct}%</span></span>
          </div>
        ) : <p className="mt-2 text-xs text-muted-foreground">Chưa lấy được giá vàng.</p>}
        {premiumHigh && (
          <p className="mt-2 flex items-start gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-600">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            Vàng SJC đang cao hơn thế giới {md?.vang?.premiumPct}% — cân nhắc rủi ro mua ở vùng chênh lệch cao.
          </p>
        )}
      </Card>
    </div>
  )
}

function AiNotesCard({ ai, loading, error }: { ai: AiResult | null; loading: boolean; error: boolean }) {
  return (
    <Card className="p-5">
      <CardLabel icon={<Sparkles className="h-3.5 w-3.5" aria-hidden />}>Diễn giải & Lưu ý</CardLabel>
      {loading ? (
        <div className="mt-3 space-y-2">{[0, 1, 2, 3].map(i => <div key={i} className="h-3 animate-pulse rounded bg-secondary" style={{ width: `${95 - i * 8}%` }} />)}</div>
      ) : ai ? (
        <div className="mt-2 space-y-3">
          <p className="text-sm leading-relaxed text-muted-foreground">{ai.sections.dienGiaiKenh}</p>
          <div className={cn('rounded-lg border px-3 py-2.5', ai.warnings.length ? 'border-amber-500/30 bg-amber-500/10' : 'border-border/60')}>
            <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-foreground">
              {ai.warnings.length ? <AlertTriangle className="h-3.5 w-3.5 text-amber-500" aria-hidden /> : <Info className="h-3.5 w-3.5" aria-hidden />}
              Lưu ý cho bạn
            </p>
            {/* Cảnh báo bắt buộc hiển thị độc lập — luôn thấy dù AI có lồng vào lời khuyên hay không. */}
            {ai.warnings.length > 0 && (
              <ul className="mb-2 space-y-1">
                {ai.warnings.map((w, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-sm font-medium text-amber-600">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />{w}
                  </li>
                ))}
              </ul>
            )}
            <p className="text-sm leading-relaxed text-muted-foreground">{ai.sections.luuY}</p>
          </div>
        </div>
      ) : error ? (
        <p className="mt-3 flex items-center gap-1.5 text-sm text-muted-foreground"><AlertCircle className="h-4 w-4" aria-hidden />Không lấy được diễn giải AI lúc này.</p>
      ) : null}
      <p className="mt-3 border-t border-border/50 pt-3 text-[11px] leading-relaxed text-muted-foreground">
        Kết quả này mang tính tham khảo, không phải lời khuyên đầu tư chính thức. Hãy cân nhắc kỹ và tham khảo chuyên gia tài chính có chứng chỉ trước các quyết định đầu tư lớn.
      </p>
    </Card>
  )
}

// ─── Trang chính ─────────────────────────────────────────────────────────────

export default function TuVanDauTuPage() {
  const [options, setOptions] = useState<TuVanOptions | null>(null)
  const [form, setForm] = useState<TuVanForm>({})
  const [step, setStep] = useState(0)
  const [errors, setErrors] = useState<Record<string, boolean>>({})

  const [result, setResult] = useState<TuVanResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ai, setAi] = useState<AiResult | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState(false)
  const [stocks, setStocks] = useState<StockBuckets | null>(null)
  const [stocksLoading, setStocksLoading] = useState(false)
  const [stocksError, setStocksError] = useState(false)
  // Khoá chống race: chỉ chấp nhận kết quả của lần submit mới nhất.
  const submitId = useRef(0)

  useEffect(() => {
    let on = true
    tuVanApi.getOptions().then(o => { if (on) setOptions(o) }).catch(() => {})
    return () => { on = false }
  }, [])

  const set = useCallback((k: string, v: string | number | string[]) => {
    setForm(f => ({ ...f, [k]: v }))
    setErrors(e => ({ ...e, [k]: false }))
  }, [])

  const stepFields = useMemo(
    () => (options?.fields || []).filter(f => STEPS[step].groups.includes(f.dataGroup)),
    [options, step],
  )

  const validateStep = () => {
    const next: Record<string, boolean> = {}
    stepFields.forEach(f => { if (f.required && isEmpty(form[f.key])) next[f.key] = true })
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const handleNext = () => { if (validateStep()) setStep(s => Math.min(s + 1, STEPS.length - 1)) }
  const handleBack = () => setStep(s => Math.max(s - 1, 0))

  const handleSubmit = async () => {
    if (!validateStep()) return
    const id = ++submitId.current  // đánh dấu lần submit này
    setSubmitting(true); setError(null)
    setAi(null); setStocks(null); setAiError(false); setStocksError(false)
    try {
      const res = await tuVanApi.suggest(form)
      if (id !== submitId.current) return  // đã có submit mới hơn
      setResult(res)
      // Gọi AI + rổ cổ phiếu song song (không chặn hiển thị số); chỉ nhận nếu còn là lần mới nhất.
      setAiLoading(true); setStocksLoading(true)
      tuVanApi.getAi(form)
        .then(a => { if (id === submitId.current) setAi(a) })
        .catch(() => { if (id === submitId.current) setAiError(true) })
        .finally(() => { if (id === submitId.current) setAiLoading(false) })
      tuVanApi.getStocks()
        .then(s => { if (id === submitId.current) setStocks(s) })
        .catch(() => { if (id === submitId.current) setStocksError(true) })
        .finally(() => { if (id === submitId.current) setStocksLoading(false) })
    } catch {
      if (id === submitId.current) setError('Không tính được tư vấn. Vui lòng kiểm tra lại thông tin và thử lại.')
    } finally {
      if (id === submitId.current) setSubmitting(false)
    }
  }

  const handleReset = () => {
    submitId.current++  // huỷ hiệu lực mọi promise đang chạy
    setResult(null); setAi(null); setStocks(null); setAiError(false); setStocksError(false)
    setStep(0); setErrors({}); setError(null)
  }

  // ── Màn kết quả ──
  if (result) {
    return (
      <>
        <PageHeader
          title="Tư vấn đầu tư"
          subtitle="Kết quả phân tích hồ sơ và gợi ý phân bổ đa kênh"
          actions={
            <button type="button" onClick={handleReset}
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <RefreshCw className="h-4 w-4" aria-hidden />Làm lại khảo sát
            </button>
          }
        />
        <div className="space-y-4">
          <RiskGroupCard r={result} />
          <AiPortraitCard ai={ai} loading={aiLoading} error={aiError} />
          <AllocationCard r={result} />
          <ChannelCards r={result} stocks={stocks} stocksLoading={stocksLoading} stocksError={stocksError} />
          <AiNotesCard ai={ai} loading={aiLoading} error={aiError} />
        </div>
      </>
    )
  }

  // ── Màn wizard ──
  return (
    <>
      <PageHeader title="Tư vấn đầu tư" subtitle="Trả lời bảng hỏi để nhận hồ sơ rủi ro và gợi ý đầu tư đa kênh (tiết kiệm, trái phiếu, cổ phiếu, vàng)" />

      {/* Thanh tiến trình */}
      <div className="mb-5 flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div key={i} className="flex flex-1 items-center gap-2">
            <div className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold',
              i < step ? 'bg-primary text-primary-foreground' : i === step ? 'bg-primary text-primary-foreground' : 'bg-secondary text-muted-foreground')}>
              {i + 1}
            </div>
            <span className={cn('hidden text-xs font-medium sm:inline', i === step ? 'text-foreground' : 'text-muted-foreground')}>{s.title}</span>
            {i < STEPS.length - 1 && <div className={cn('h-0.5 flex-1 rounded', i < step ? 'bg-primary' : 'bg-border')} />}
          </div>
        ))}
      </div>

      <Card className="p-5">
        <div className="mb-4">
          <h2 className="font-heading text-lg font-semibold text-foreground">{STEPS[step].title}</h2>
          <p className="text-sm text-muted-foreground">{STEPS[step].subtitle}</p>
        </div>

        {!options ? (
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" aria-hidden />{VI.common.loading}</div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {stepFields.map(f => (
              <FieldInput key={f.key} field={f} value={form[f.key]} error={errors[f.key]} onChange={v => set(f.key, v)} />
            ))}
          </div>
        )}

        {error && (
          <p className="mt-4 flex items-center gap-1.5 text-sm text-down"><AlertCircle className="h-4 w-4" aria-hidden />{error}</p>
        )}

        <div className="mt-6 flex items-center justify-between">
          <button type="button" onClick={handleBack} disabled={step === 0}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <ChevronLeft className="h-4 w-4" aria-hidden />Quay lại
          </button>
          {step < STEPS.length - 1 ? (
            <button type="button" onClick={handleNext} disabled={!options}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              Tiếp theo<ChevronRight className="h-4 w-4" aria-hidden />
            </button>
          ) : (
            <button type="button" onClick={handleSubmit} disabled={submitting || !options}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Sparkles className="h-4 w-4" aria-hidden />}
              {submitting ? 'Đang phân tích…' : 'Xem tư vấn của tôi'}
            </button>
          )}
        </div>
      </Card>

      <p className="mt-3 flex items-center justify-center gap-1.5 text-center text-[11px] text-muted-foreground">
        <Compass className="h-3 w-3" aria-hidden />Hồ sơ chỉ dùng để tính gợi ý, không lưu thông tin nhận dạng cá nhân.
      </p>
    </>
  )
}
