import apiClient from './index'
import { toCamelCase } from './utils'
import type { BondOverview, BondHistory } from '@/types/bond'

export const bondApi = {
  /** Lãi suất điều hành (SBV/Fed) + lợi suất trái phiếu (US10Y live, VN10Y tham khảo). */
  async getOverview(): Promise<BondOverview> {
    const res = await apiClient.get<Record<string, unknown>>('/api/v1/bond/overview')
    return toCamelCase<BondOverview>(res.data)
  },

  /** Lịch sử lợi suất trái phiếu Mỹ 10 năm. */
  async getHistory(days = 365): Promise<BondHistory> {
    const res = await apiClient.get<Record<string, unknown>>('/api/v1/bond/history', { params: { days } })
    return toCamelCase<BondHistory>(res.data)
  },
}
