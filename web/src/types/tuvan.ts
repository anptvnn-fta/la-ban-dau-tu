// Kiểu dữ liệu cho trang Tư vấn đầu tư đa kênh. Khớp api/v1/.../tu_van.

export type DataGroup = 'nhan_khau' | 'tai_chinh' | 'muc_tieu' | 'rui_ro' | 'hanh_vi'

export interface FieldOption {
  key: string
  label: string
}

export interface TuVanField {
  key: string
  label: string
  type: 'select' | 'number' | 'text'
  dataGroup: DataGroup
  required: boolean
  dimension: 'none' | 'capacity' | 'tolerance'
  multi: boolean
  note?: string | null
  options?: FieldOption[]
  min?: number
  max?: number
}

export interface TuVanOptions {
  fields: TuVanField[]
}

/** Giá trị form: key trường (snake_case) → giá trị. Multi-select là mảng. */
export type TuVanForm = Record<string, string | number | string[] | undefined>

export interface AllocationItem {
  assetClass: 'tiet_kiem' | 'trai_phieu' | 'co_phieu' | 'vang'
  label: string
  percent: number
  amountTrieu?: number | null
  role: string
}

export interface StockSplitItem {
  bucket: 'on_dinh' | 'trung_binh' | 'rui_ro'
  label: string
  withinStockPct: number
  portfolioPct: number
}

export interface SavingsTop {
  bank: string
  rate: number
}

export interface MarketData {
  tietKiem?: { termMonths: number; top: SavingsTop[]; sbvPolicyRate?: number | null } | null
  traiPhieu?: { sbvPolicyRate?: number | null; usYield?: number | null; vn10yRef?: number | null } | null
  vang?: { sjcBuy?: number | null; sjcSell?: number | null; worldPerLuongVnd?: number | null; premiumPct?: number | null } | null
  warnings?: string[]
}

export interface TuVanResult {
  generatedAt: string
  age?: number | null
  vonMidpointTrieu?: number | null
  capacity: { raw: number; score: number; group: string; label: string }
  tolerance: { total: number; group: string; label: string; forcedDefensive: boolean }
  finalGroup: string
  finalLabel: string
  finalEn: string
  finalDesc: string
  forcedDefensive: boolean
  timeTilt: string
  years?: number | null
  allocation: AllocationItem[]
  stockSplit: StockSplitItem[]
  marketData?: MarketData
}

export interface AiResult {
  sections: { chanDung: string; lyDoNhom: string; dienGiaiKenh: string; luuY: string }
  source: 'ai' | 'fallback'
  warnings: string[]
}

export interface StockPick {
  symbol: string
  volatilityPct: number
  bucket: string
}

export interface StockBuckets {
  generatedAt: string
  buckets: { bucket: string; label: string; stocks: StockPick[] }[]
  dataWarning?: string | null
}
