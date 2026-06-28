// Kiểu dữ liệu cho trang Xăng Dầu (giai đoạn C). Khớp api/v1/schemas/petrol.py.

export interface PetrolFuel {
  code: string
  name: string
  price?: number | null
  prevPrice?: number | null
  change?: number | null
  changePct?: number | null
}

export interface PetrolOverview {
  generatedAt: string
  effectiveDate?: string | null
  nextAdjustment?: string | null
  fuels: PetrolFuel[]
  brentUsd?: number | null
  wtiUsd?: number | null
  cycleNote?: string | null
  dataWarning?: string | null
}

export interface PetrolHistoryPoint {
  date: string
  e5?: number | null
  ron95?: number | null
  do?: number | null
  brent?: number | null
}

export interface PetrolHistory {
  generatedAt: string
  days: number
  points: PetrolHistoryPoint[]
  dataWarning?: string | null
}
