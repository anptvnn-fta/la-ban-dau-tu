import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  BacktestRunRequest,
  BacktestRunResponse,
  BacktestResultsResponse,
  BacktestResultItem,
  PerformanceMetrics,
  BacktestPhaseFilter,
  WalkForwardResponse,
} from '../types/backtest';

// ============ API ============

export const backtestApi = {
  /**
   * Trigger backtest evaluation
   */
  /**
   * Kiểm định trượt tiến: đánh giá tín hiệu kỹ thuật trên dữ liệu lịch sử (kết quả ngay).
   */
  walkForward: async (code: string, evalWindowDays = 10): Promise<WalkForwardResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/walk-forward',
      { code, eval_window_days: evalWindowDays },
    );
    return toCamelCase<WalkForwardResponse>(response.data);
  },

  /** Kiểm định trượt tiến bằng AI (tốn một ít lượt LLM). */
  walkForwardAi: async (code: string, evalWindowDays = 10): Promise<WalkForwardResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/walk-forward-ai',
      { code, eval_window_days: evalWindowDays },
    );
    return toCamelCase<WalkForwardResponse>(response.data);
  },

  /** Lấy kết quả kiểm định trượt tiến đã lưu (không chạy lại). */
  getSavedWalkForward: async (code: string, evalWindowDays = 10, mode: 'tech' | 'ai' = 'tech'): Promise<WalkForwardResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/backtest/walk-forward/saved',
      { params: { code, eval_window_days: evalWindowDays, mode } },
    );
    return toCamelCase<WalkForwardResponse>(response.data);
  },

  run: async (params: BacktestRunRequest = {}): Promise<BacktestRunResponse> => {
    const requestData: Record<string, unknown> = {};
    if (params.code?.trim()) requestData.code = params.code.trim();
    if (params.force) requestData.force = params.force;
    if (params.evalWindowDays != null) requestData.eval_window_days = params.evalWindowDays;
    if (params.minAgeDays != null) requestData.min_age_days = params.minAgeDays;
    if (params.analysisDateFrom) requestData.analysis_date_from = params.analysisDateFrom;
    if (params.analysisDateTo) requestData.analysis_date_to = params.analysisDateTo;
    if (params.limit != null) requestData.limit = params.limit;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/run',
      requestData,
    );
    return toCamelCase<BacktestRunResponse>(response.data);
  },

  /**
   * Get paginated backtest results
   */
  getResults: async (params: {
    code?: string;
    evalWindowDays?: number;
    analysisDateFrom?: string;
    analysisDateTo?: string;
    analysisPhase?: BacktestPhaseFilter;
    page?: number;
    limit?: number;
  } = {}): Promise<BacktestResultsResponse> => {
    const { code, evalWindowDays, analysisDateFrom, analysisDateTo, analysisPhase, page = 1, limit = 20 } = params;

    const queryParams: Record<string, string | number> = { page, limit };
    if (code) queryParams.code = code;
    if (evalWindowDays) queryParams.eval_window_days = evalWindowDays;
    if (analysisDateFrom) queryParams.analysis_date_from = analysisDateFrom;
    if (analysisDateTo) queryParams.analysis_date_to = analysisDateTo;
    if (analysisPhase && analysisPhase !== 'all') queryParams.analysis_phase = analysisPhase;

    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/backtest/results',
      { params: queryParams },
    );

    const data = toCamelCase<BacktestResultsResponse>(response.data);
    return {
      total: data.total,
      page: data.page,
      limit: data.limit,
      items: (data.items || []).map(item => toCamelCase<BacktestResultItem>(item)),
    };
  },

  /**
   * Get overall performance metrics
   */
  getOverallPerformance: async (params: {
    evalWindowDays?: number;
    analysisDateFrom?: string;
    analysisDateTo?: string;
    analysisPhase?: BacktestPhaseFilter;
  } = {}): Promise<PerformanceMetrics | null> => {
    try {
      const queryParams: Record<string, string | number> = {};
      if (params.evalWindowDays) queryParams.eval_window_days = params.evalWindowDays;
      if (params.analysisDateFrom) queryParams.analysis_date_from = params.analysisDateFrom;
      if (params.analysisDateTo) queryParams.analysis_date_to = params.analysisDateTo;
      if (params.analysisPhase && params.analysisPhase !== 'all') queryParams.analysis_phase = params.analysisPhase;
      const response = await apiClient.get<Record<string, unknown>>(
        '/api/v1/backtest/performance',
        { params: queryParams },
      );
      return toCamelCase<PerformanceMetrics>(response.data);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 404) return null;
      }
      throw err;
    }
  },

  /**
   * Get per-stock performance metrics
   */
  getStockPerformance: async (code: string, params: {
    evalWindowDays?: number;
    analysisDateFrom?: string;
    analysisDateTo?: string;
    analysisPhase?: BacktestPhaseFilter;
  } = {}): Promise<PerformanceMetrics | null> => {
    try {
      const queryParams: Record<string, string | number> = {};
      if (params.evalWindowDays) queryParams.eval_window_days = params.evalWindowDays;
      if (params.analysisDateFrom) queryParams.analysis_date_from = params.analysisDateFrom;
      if (params.analysisDateTo) queryParams.analysis_date_to = params.analysisDateTo;
      if (params.analysisPhase && params.analysisPhase !== 'all') queryParams.analysis_phase = params.analysisPhase;
      const response = await apiClient.get<Record<string, unknown>>(
        `/api/v1/backtest/performance/${encodeURIComponent(code)}`,
        { params: queryParams },
      );
      return toCamelCase<PerformanceMetrics>(response.data);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 404) return null;
      }
      throw err;
    }
  },
};
