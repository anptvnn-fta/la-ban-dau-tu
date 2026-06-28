import apiClient from './index'
import { toCamelCase } from './utils'
import type { PetrolOverview, PetrolHistory } from '@/types/petrol'

export const petrolApi = {
  /** Giá xăng dầu hiện tại, kỳ điều hành kế, dầu thế giới. */
  async getOverview(): Promise<PetrolOverview> {
    const res = await apiClient.get<Record<string, unknown>>('/api/v1/petrol/overview')
    return toCamelCase<PetrolOverview>(res.data)
  },

  /** Lịch sử giá xăng VN + Brent quy chiếu. */
  async getHistory(days = 365): Promise<PetrolHistory> {
    const res = await apiClient.get<Record<string, unknown>>('/api/v1/petrol/history', {
      params: { days },
    })
    return toCamelCase<PetrolHistory>(res.data)
  },
}
