// Kiểu dữ liệu cho trang Tiết Kiệm (giai đoạn B). Khớp api/v1/schemas/savings.py.

export interface SavingsBank {
  name: string
  symbol?: string | null
  rates: (number | null)[] // theo thứ tự `terms`
}

export interface SavingsBest {
  term: number
  bank: string
  rate: number
}

export interface SavingsOverview {
  generatedAt: string
  terms: number[]
  banks: SavingsBank[]
  best: SavingsBest[]
  sbvPolicyRate?: number | null
  note?: string | null
  dataWarning?: string | null
}
