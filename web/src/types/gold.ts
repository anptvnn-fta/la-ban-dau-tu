// Kiểu dữ liệu cho trang Vàng (Phase A — đa tài sản).
// Khớp với api/v1/schemas/gold.py sau khi toCamelCase.

export interface GoldType {
  name: string
  karat?: string | null
  buy?: number | null
  sell?: number | null
}

export interface GoldOverview {
  generatedAt: string
  sjcName?: string | null
  sjcBranch?: string | null
  sjcBuy?: number | null
  sjcSell?: number | null
  sjcDate?: string | null
  bidAskSpread?: number | null
  worldUsdOz?: number | null
  worldSource?: string | null
  usdVnd?: number | null
  worldPerLuongVnd?: number | null
  premiumVnd?: number | null
  premiumPct?: number | null
  assessment?: string | null
  goldTypes?: GoldType[] | null
  dataWarning?: string | null
}

export interface GoldHistoryPoint {
  date: string
  sjc?: number | null
  world?: number | null
  premiumPct?: number | null
}

export interface GoldHistory {
  generatedAt: string
  days: number
  usdVnd?: number | null
  points: GoldHistoryPoint[]
  premiumCurrentPct?: number | null
  premiumAvgPct?: number | null
  premiumMinPct?: number | null
  premiumMaxPct?: number | null
  dataWarning?: string | null
}
