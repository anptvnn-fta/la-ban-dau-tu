import apiClient from './index'
import { toCamelCase } from './utils'
import type { GoldOverview, GoldHistory } from '@/types/gold'

export const goldApi = {
  /** Tổng quan vàng: giá SJC, giá thế giới, tỷ giá, chênh lệch (premium), bảng loại vàng. */
  async getOverview(): Promise<GoldOverview> {
    const res = await apiClient.get<Record<string, unknown>>('/api/v1/gold/overview')
    return toCamelCase<GoldOverview>(res.data)
  },

  /** Lịch sử giá vàng SJC + thế giới quy đổi (VND/lượng). Lần đầu có thể chậm vài giây. */
  async getHistory(days = 180, stepDays = 14): Promise<GoldHistory> {
    const res = await apiClient.get<Record<string, unknown>>('/api/v1/gold/history', {
      params: { days, step_days: stepDays },
    })
    return toCamelCase<GoldHistory>(res.data)
  },
}
