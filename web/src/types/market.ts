// Kiểu dữ liệu cho trang Tổng Quan Thị Trường (U3).
// Khớp với api/v1/schemas/market.py sau khi toCamelCase.

export interface MarketIndex {
  code: string
  name: string
  current?: number | null
  change?: number | null
  changePct?: number | null
  high?: number | null
  low?: number | null
  volume?: number | null
}

export interface MarketMover {
  code: string
  name?: string | null
  price?: number | null
  changePct?: number | null
  value?: number | null
}

export interface MarketSector {
  name: string
  changePct?: number | null
  count: number
  codes: string[]
}

export interface MarketBreadth {
  advancers: number
  decliners: number
  unchanged: number
  universeSize: number
  totalValue?: number | null
}

export interface MarketOverview {
  generatedAt: string
  universeLabel: string
  indices: MarketIndex[]
  breadth?: MarketBreadth | null
  topGainers: MarketMover[]
  topLosers: MarketMover[]
  sectors: MarketSector[]
  dataWarning?: string | null
}
