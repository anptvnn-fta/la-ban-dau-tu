import apiClient from './index'
import { toCamelCase } from './utils'
import type { MarketOverview } from '@/types/market'

export const marketApi = {
  /** Tổng quan thị trường: chỉ số, top tăng/giảm, độ rộng, nhóm ngành. */
  async getOverview(): Promise<MarketOverview> {
    const res = await apiClient.get<Record<string, unknown>>('/api/v1/market/overview')
    return toCamelCase<MarketOverview>(res.data)
  },
}
