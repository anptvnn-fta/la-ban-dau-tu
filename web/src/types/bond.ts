// Kiểu dữ liệu cho trang Trái Phiếu (giai đoạn B). Khớp api/v1/schemas/bond.py.

export interface BondOverview {
  generatedAt: string
  sbvPolicyRate?: number | null
  fedLow?: number | null
  fedHigh?: number | null
  usYield?: number | null
  vn10yRef?: number | null
  spreadSbvFed?: number | null
  spreadVnUs?: number | null
  note?: string | null
  dataWarning?: string | null
}

export interface BondHistoryPoint {
  date: string
  usYield?: number | null
}

export interface BondHistory {
  generatedAt: string
  days: number
  points: BondHistoryPoint[]
  dataWarning?: string | null
}
