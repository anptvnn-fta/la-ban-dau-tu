import apiClient from './index';
import { toCamelCase } from './utils';

export type ExtractItem = {
  code?: string | null;
  name?: string | null;
  confidence: string;
};

export type ExtractFromImageResponse = {
  codes: string[];
  items?: ExtractItem[];
  rawText?: string;
};

/** Một nến (OHLC) trong dữ liệu lịch sử, kèm chỉ báo kỹ thuật (tuỳ chọn). */
export interface OhlcBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  amount?: number;
  changePercent?: number;
  ma5?: number;
  ma10?: number;
  ma20?: number;
  rsi?: number;
  macd?: number;
  macdSignal?: number;
}

export interface StockHistoryResponse {
  stockCode: string;
  stockName?: string;
  period: string;
  data: OhlcBar[];
}

/** Một ngày giao dịch khối ngoại. */
export interface ForeignFlowBar {
  date: string;
  netVolume?: number;
  netValue?: number;
  buyVolume?: number;
  sellVolume?: number;
  roomPct?: number;
}

export interface ForeignFlowResponse {
  stockCode: string;
  data: ForeignFlowBar[];
}

export const stocksApi = {
  /** Lấy dữ liệu nến (OHLC) cho biểu đồ giá, kèm chỉ báo kỹ thuật. */
  async getHistory(
    stockCode: string,
    days = 120,
    period: 'daily' | 'weekly' | 'monthly' = 'daily',
    indicators = true,
  ): Promise<StockHistoryResponse> {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/stocks/${encodeURIComponent(stockCode)}/history`,
      { params: { period, days, indicators } },
    );
    return toCamelCase<StockHistoryResponse>(response.data);
  },

  /** Lấy chuỗi giao dịch khối ngoại theo ngày. */
  async getForeignFlow(stockCode: string, days = 30): Promise<ForeignFlowResponse> {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/stocks/${encodeURIComponent(stockCode)}/foreign-flow`,
      { params: { days } },
    );
    return toCamelCase<ForeignFlowResponse>(response.data);
  },

  async extractFromImage(file: File): Promise<ExtractFromImageResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
    const response = await apiClient.post(
      '/api/v1/stocks/extract-from-image',
      formData,
      {
        headers,
        timeout: 60000, // Vision API can be slow; 60s
      },
    );

    const data = response.data as { codes?: string[]; items?: ExtractItem[]; raw_text?: string };
    return {
      codes: data.codes ?? [],
      items: data.items,
      rawText: data.raw_text,
    };
  },

  async parseImport(file?: File, text?: string): Promise<ExtractFromImageResponse> {
    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
      const response = await apiClient.post('/api/v1/stocks/parse-import', formData, { headers });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    if (text) {
      const response = await apiClient.post('/api/v1/stocks/parse-import', { text });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    throw new Error('Vui lòng cung cấp tệp hoặc dán văn bản');
  },
};
