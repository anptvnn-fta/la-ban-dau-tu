import apiClient from './index'
import { toCamelCase } from './utils'
import type { TuVanOptions, TuVanForm, TuVanResult, AiResult, StockBuckets } from '@/types/tuvan'

export const tuVanApi = {
  /** Định nghĩa 26 trường hồ sơ để dựng wizard. */
  async getOptions(): Promise<TuVanOptions> {
    const res = await apiClient.get<Record<string, unknown>>('/api/v1/tu-van/options')
    return toCamelCase<TuVanOptions>(res.data)
  },

  /** Chấm điểm 2 thang + nhóm cuối + phân bổ đa kênh + dữ liệu live (không AI). */
  async suggest(form: TuVanForm): Promise<TuVanResult> {
    const res = await apiClient.post<Record<string, unknown>>('/api/v1/tu-van/suggest', form)
    return toCamelCase<TuVanResult>(res.data)
  },

  /** 3 rổ biến động cổ phiếu. */
  async getStocks(): Promise<StockBuckets> {
    const res = await apiClient.get<Record<string, unknown>>('/api/v1/tu-van/stocks')
    return toCamelCase<StockBuckets>(res.data)
  },

  /** AI phân tích chân dung + diễn giải (4 đoạn). */
  async getAi(form: TuVanForm): Promise<AiResult> {
    const res = await apiClient.post<Record<string, unknown>>('/api/v1/tu-van/ai', form)
    return toCamelCase<AiResult>(res.data)
  },
}
