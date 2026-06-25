import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  HistoryListResponse,
  HistoryItem,
  HistoryFilters,
  AnalysisReport,
  NewsIntelResponse,
  NewsIntelItem,
  RunDiagnosticSummary,
  StockBarResponse,
} from '../types/analysis';
import type { RunFlowSnapshot } from '../types/runFlow';

// ============ API ============

export interface GetHistoryListParams extends HistoryFilters {
  page?: number;
  limit?: number;
}

export const historyApi = {
  /**
   * Lấy danh sách lịch sử phân tích
   * @param params Tham số lọc và phân trang
   */
  getList: async (params: GetHistoryListParams = {}): Promise<HistoryListResponse> => {
    const { stockCode, reportType, startDate, endDate, page = 1, limit = 20 } = params;

    const queryParams: Record<string, string | number> = { page, limit };
    if (stockCode) queryParams.stock_code = stockCode;
    if (reportType) queryParams.report_type = reportType;
    if (startDate) queryParams.start_date = startDate;
    if (endDate) queryParams.end_date = endDate;

    const response = await apiClient.get<Record<string, unknown>>('/api/v1/history', {
      params: queryParams,
    });

    const data = toCamelCase<{ total: number; page: number; limit: number; items: HistoryItem[] }>(response.data);
    return {
      total: data.total,
      page: data.page,
      limit: data.limit,
      items: data.items.map(item => toCamelCase<HistoryItem>(item)),
    };
  },

  /**
   * Lấy chi tiết báo cáo lịch sử
   * @param recordId ID bản ghi lịch sử phân tích
   */
  getDetail: async (recordId: number): Promise<AnalysisReport> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}`);
    return toCamelCase<AnalysisReport>(response.data);
  },

  /**
   * Lấy tin tức liên quan đến báo cáo lịch sử
   * @param recordId ID bản ghi lịch sử phân tích
   * @param limit Giới hạn số lượng trả về
   */
  getNews: async (recordId: number, limit = 20): Promise<NewsIntelResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/news`, {
      params: { limit },
    });

    const data = toCamelCase<NewsIntelResponse>(response.data);
    return {
      total: data.total,
      items: (data.items || []).map(item => toCamelCase<NewsIntelItem>(item)),
    };
  },

  /**
   * Lấy nội dung Markdown của báo cáo lịch sử
   * @param recordId ID bản ghi lịch sử phân tích
   * @returns Nội dung báo cáo đầy đủ dạng Markdown
   */
  getMarkdown: async (recordId: number): Promise<string> => {
    const response = await apiClient.get<{ content: string }>(`/api/v1/history/${recordId}/markdown`);
    return response.data.content;
  },

  /**
   * Lấy tóm tắt chẩn đoán chạy của báo cáo lịch sử
   * @param recordId ID bản ghi lịch sử phân tích
   */
  getDiagnostics: async (recordId: number): Promise<RunDiagnosticSummary> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/diagnostics`);
    return toCamelCase<RunDiagnosticSummary>(response.data);
  },

  /**
   * Lấy snapshot luồng chạy của báo cáo lịch sử
   * @param recordId ID bản ghi lịch sử phân tích
   */
  getRecordFlow: async (recordId: number): Promise<RunFlowSnapshot> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/flow`);
    return toCamelCase<RunFlowSnapshot>(response.data);
  },

  /**
   * Xóa hàng loạt bản ghi lịch sử
   * @param recordIds Danh sách ID bản ghi cần xóa
   */
  deleteRecords: async (recordIds: number[]): Promise<{ deleted: number }> => {
    const response = await apiClient.delete<Record<string, unknown>>('/api/v1/history', {
      data: { record_ids: recordIds },
    });

    return toCamelCase<{ deleted: number }>(response.data);
  },

  /**
   * Xóa tất cả lịch sử theo mã cổ phiếu
   * @param stockCode Mã cổ phiếu
   */
  deleteByCode: async (stockCode: string): Promise<{ deleted: number }> => {
    const response = await apiClient.delete<Record<string, unknown>>(`/api/v1/history/by-code/${encodeURIComponent(stockCode)}`);
    return toCamelCase<{ deleted: number }>(response.data);
  },

  /**
   * Lấy danh sách thanh cổ phiếu (không trùng mã, không bao gồm diễn biến thị trường)
   */
  getStockBarList: async (params: {
    startDate?: string;
    endDate?: string;
    limit?: number;
  } = {}): Promise<StockBarResponse> => {
    const queryParams: Record<string, string | number> = {};
    if (params.startDate) queryParams.start_date = params.startDate;
    if (params.endDate) queryParams.end_date = params.endDate;
    if (params.limit) queryParams.limit = params.limit;

    const response = await apiClient.get<Record<string, unknown>>('/api/v1/history/stocks', {
      params: queryParams,
    });

    const data = toCamelCase<{ total: number; items: unknown[] }>(response.data);
    return {
      total: data.total,
      items: data.items.map(item => toCamelCase<Record<string, unknown>>(item) as unknown as typeof data.items[0]),
    } as StockBarResponse;
  },
};
