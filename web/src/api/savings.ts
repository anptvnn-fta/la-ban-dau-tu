import apiClient from './index'
import { toCamelCase } from './utils'
import type { SavingsOverview } from '@/types/savings'

export const savingsApi = {
  /** Bảng lãi suất tiết kiệm theo ngân hàng × kỳ hạn + lãi suất tốt nhất. */
  async getOverview(): Promise<SavingsOverview> {
    const res = await apiClient.get<Record<string, unknown>>('/api/v1/savings/overview')
    return toCamelCase<SavingsOverview>(res.data)
  },
}
