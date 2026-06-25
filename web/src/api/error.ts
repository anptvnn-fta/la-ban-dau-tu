import axios from 'axios';

export type ApiErrorCategory =
  | 'agent_disabled'
  | 'missing_params'
  | 'llm_not_configured'
  | 'model_tool_incompatible'
  | 'invalid_tool_call'
  | 'portfolio_oversell'
  | 'portfolio_busy'
  | 'upstream_llm_400'
  | 'upstream_timeout'
  | 'upstream_network'
  | 'local_connection_failed'
  | 'http_error'
  | 'unknown';

export interface ParsedApiError {
  title: string;
  message: string;
  rawMessage: string;
  status?: number;
  category: ApiErrorCategory;
}

type ResponseLike = {
  status?: number;
  data?: unknown;
  statusText?: string;
};

type ErrorCarrier = {
  response?: ResponseLike;
  code?: string;
  message?: string;
  parsedError?: ParsedApiError;
  cause?: unknown;
};

type CreateParsedApiErrorOptions = {
  title: string;
  message: string;
  rawMessage?: string;
  status?: number;
  category?: ApiErrorCategory;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function pickString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

function stringifyValue(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'string') {
    return value.trim() || null;
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function getResponse(error: unknown): ResponseLike | undefined {
  if (!isRecord(error)) {
    return undefined;
  }

  const response = (error as ErrorCarrier).response;
  return response && typeof response === 'object' ? response : undefined;
}

function getErrorCode(error: unknown): string | undefined {
  return isRecord(error) && typeof (error as ErrorCarrier).code === 'string'
    ? (error as ErrorCarrier).code
    : undefined;
}

function getErrorMessage(error: unknown): string | null {
  if (typeof error === 'string') {
    return error.trim() || null;
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }

  if (isRecord(error) && typeof (error as ErrorCarrier).message === 'string') {
    const message = (error as ErrorCarrier).message?.trim();
    return message || null;
  }

  return null;
}

function getCauseMessage(error: unknown): string | null {
  if (!isRecord(error)) {
    return null;
  }

  return getErrorMessage((error as ErrorCarrier).cause);
}

function buildMatchText(parts: Array<string | undefined | null>): string {
  return parts
    .filter((part): part is string => typeof part === 'string' && part.trim().length > 0)
    .join(' | ')
    .toLowerCase();
}

function includesAny(haystack: string, needles: string[]): boolean {
  return needles.some((needle) => haystack.includes(needle.toLowerCase()));
}

function extractValidationDetail(detail: unknown): string | null {
  if (!Array.isArray(detail)) {
    return null;
  }

  const parts = detail
    .map((item) => {
      if (!isRecord(item)) {
        return stringifyValue(item);
      }

      const location = Array.isArray(item.loc)
        ? item.loc.map((segment) => String(segment)).join('.')
        : null;
      const message = pickString(item.msg, item.message, item.error);
      if (!location && !message) {
        return stringifyValue(item);
      }
      return [location, message].filter(Boolean).join(': ');
    })
    .filter((entry): entry is string => Boolean(entry));

  return parts.length > 0 ? parts.join('; ') : null;
}

function extractErrorCode(data: unknown): string | null {
  if (!isRecord(data)) {
    return null;
  }

  const detail = data.detail;
  if (isRecord(detail)) {
    return pickString(detail.error, detail.code, data.error, data.code);
  }

  return pickString(data.error, data.code);
}

export function extractErrorPayloadText(data: unknown): string | null {
  if (typeof data === 'string') {
    return data.trim() || null;
  }

  if (Array.isArray(data)) {
    return extractValidationDetail(data) ?? stringifyValue(data);
  }

  if (!isRecord(data)) {
    return stringifyValue(data);
  }

  const detail = data.detail;
  if (isRecord(detail)) {
    return (
      pickString(detail.message, detail.error)
      ?? extractValidationDetail(detail.detail)
      ?? stringifyValue(detail)
    );
  }

  return (
    pickString(
      detail,
      data.message,
      data.error,
      data.title,
      data.reason,
      data.description,
      data.msg,
    )
    ?? extractValidationDetail(detail)
    ?? stringifyValue(data)
  );
}

export function createParsedApiError(options: CreateParsedApiErrorOptions): ParsedApiError {
  return {
    title: options.title,
    message: options.message,
    rawMessage: options.rawMessage?.trim() || options.message,
    status: options.status,
    category: options.category ?? 'unknown',
  };
}

export function isParsedApiError(value: unknown): value is ParsedApiError {
  return isRecord(value)
    && typeof value.title === 'string'
    && typeof value.message === 'string'
    && typeof value.rawMessage === 'string'
    && typeof value.category === 'string';
}

export function isApiRequestError(
  value: unknown,
): value is Error & ErrorCarrier & { parsedError: ParsedApiError } {
  return value instanceof Error
    && isRecord(value)
    && isParsedApiError((value as ErrorCarrier).parsedError);
}

export function formatParsedApiError(parsed: ParsedApiError): string {
  if (!parsed.title.trim()) {
    return parsed.message;
  }
  if (parsed.title === parsed.message) {
    return parsed.title;
  }
  return `${parsed.title}：${parsed.message}`;
}

export function getParsedApiError(error: unknown): ParsedApiError {
  if (isParsedApiError(error)) {
    return error;
  }
  if (isRecord(error) && isParsedApiError((error as ErrorCarrier).parsedError)) {
    return (error as ErrorCarrier).parsedError as ParsedApiError;
  }
  return parseApiError(error);
}

export function createApiError(
  parsed: ParsedApiError,
  extra: { response?: ResponseLike; code?: string; cause?: unknown } = {},
): Error & ErrorCarrier & { status?: number; category: ApiErrorCategory; rawMessage: string } {
  const apiError = new Error(formatParsedApiError(parsed)) as Error & ErrorCarrier & {
    status?: number;
    category: ApiErrorCategory;
    rawMessage: string;
  };
  apiError.name = 'ApiRequestError';
  apiError.parsedError = parsed;
  apiError.response = extra.response;
  apiError.code = extra.code;
  apiError.status = parsed.status;
  apiError.category = parsed.category;
  apiError.rawMessage = parsed.rawMessage;
  if (extra.cause !== undefined) {
    apiError.cause = extra.cause;
  }
  return apiError;
}

export function attachParsedApiError(error: unknown): ParsedApiError {
  const parsed = parseApiError(error);
  if (isRecord(error)) {
    const carrier = error as ErrorCarrier;
    carrier.parsedError = parsed;
  }
  if (error instanceof Error) {
    error.name = 'ApiRequestError';
    error.message = formatParsedApiError(parsed);
  }
  return parsed;
}

export function isLocalConnectionFailure(error: unknown): boolean {
  return parseApiError(error).category === 'local_connection_failed';
}

export function parseApiError(error: unknown): ParsedApiError {
  const response = getResponse(error);
  const status = response?.status;
  const payloadText = extractErrorPayloadText(response?.data);
  const errorCode = extractErrorCode(response?.data);
  const errorMessage = getErrorMessage(error);
  const causeMessage = getCauseMessage(error);
  const code = getErrorCode(error);
  const rawMessage = pickString(payloadText, response?.statusText, errorMessage, causeMessage, code)
    ?? 'Yêu cầu không thành công, vui lòng thử lại sau.';
  const matchText = buildMatchText([rawMessage, errorMessage, causeMessage, code, errorCode, response?.statusText]);

  if (includesAny(matchText, ['agent mode is not enabled', 'agent_mode'])) {
    return createParsedApiError({
      title: 'Chế độ Agent chưa được bật',
      message: 'Tính năng này yêu cầu chế độ Agent, vui lòng bật trước khi tiếp tục.',
      rawMessage,
      status,
      category: 'agent_disabled',
    });
  }

  const hasStockCodeField = includesAny(matchText, ['stock_code', 'stock_codes']);
  const hasMissingParamText = includesAny(matchText, ['必须提供 stock_code 或 stock_codes', 'missing', 'required']);
  if (hasStockCodeField && hasMissingParamText) {
    return createParsedApiError({
      title: 'Thiếu tham số bắt buộc',
      message: 'Vui lòng nhập mã cổ phiếu hoặc thông tin cần thiết trước khi thử lại.',
      rawMessage,
      status,
      category: 'missing_params',
    });
  }

  if (errorCode === 'portfolio_oversell' || includesAny(matchText, ['oversell detected'])) {
    return createParsedApiError({
      title: 'Số lượng bán vượt quá vị thế hiện có',
      message: 'Số lượng bán vượt quá vị thế khả dụng, vui lòng xóa hoặc sửa lại giao dịch bán tương ứng rồi thử lại.',
      rawMessage,
      status,
      category: 'portfolio_oversell',
    });
  }

  if (errorCode === 'portfolio_busy' || includesAny(matchText, ['portfolio ledger is busy'])) {
    return createParsedApiError({
      title: 'Sổ danh mục đang bận',
      message: 'Sổ danh mục đang xử lý một thay đổi khác, vui lòng thử lại sau.',
      rawMessage,
      status,
      category: 'portfolio_busy',
    });
  }

  if (errorCode === 'alphasift_install_failed') {
    return createParsedApiError({
      title: 'Cài đặt lại AlphaSift thất bại',
      message: 'DSA đã thử cài đặt lại AlphaSift nhưng pip không thành công. Vui lòng kiểm tra ALPHASIFT_INSTALL_SPEC, proxy mạng hoặc môi trường Python backend.',
      rawMessage,
      status,
      category: 'http_error',
    });
  }

  if (errorCode === 'alphasift_install_spec_missing') {
    return createParsedApiError({
      title: 'Chưa cấu hình nguồn cài đặt AlphaSift',
      message: 'Vui lòng xác nhận phụ thuộc backend đã được cài đặt; nếu muốn dùng tính năng cài lại, hãy cấu hình ALPHASIFT_INSTALL_SPEC.',
      rawMessage,
      status,
      category: 'http_error',
    });
  }

  if (errorCode === 'alphasift_install_spec_not_allowed') {
    return createParsedApiError({
      title: 'Nguồn cài đặt AlphaSift bị hạn chế',
      message: 'Tính năng cài lại chỉ cho phép nguồn GitHub đáng tin cậy của AlphaSift; nếu dùng đường dẫn cục bộ hoặc wheel, vui lòng cài thủ công vào môi trường Python hiện tại.',
      rawMessage,
      status,
      category: 'http_error',
    });
  }

  if (errorCode === 'alphasift_unavailable' || includesAny(matchText, ['cannot import alphasift', 'alphasift.screen'])) {
    return createParsedApiError({
      title: 'AlphaSift chưa sẵn sàng',
      message: rawMessage,
      rawMessage,
      status,
      category: 'http_error',
    });
  }

  if (errorCode === 'alphasift_adapter_unavailable') {
    return createParsedApiError({
      title: 'Lớp tích hợp AlphaSift không khả dụng',
      message: 'Phiên bản AlphaSift hiện tại thiếu lớp tích hợp ổn định với DSA. Vui lòng cài lại hoặc nâng cấp AlphaSift rồi thử lại.',
      category: 'http_error',
      rawMessage,
      status,
    });
  }

  if (errorCode === 'alphasift_screen_task_not_found') {
    return createParsedApiError({
      title: 'Không thể khôi phục tác vụ lọc cổ phiếu',
      message: 'Backend không tìm thấy tác vụ lọc này, có thể backend đã khởi động lại hoặc bản ghi đã bị dọn dẹp. Vui lòng chạy lại lệnh lọc cổ phiếu.',
      rawMessage,
      status,
      category: 'http_error',
    });
  }

  if (errorCode === 'alphasift_screen_failed') {
    return createParsedApiError({
      title: 'AlphaSift lọc cổ phiếu thất bại',
      message: 'AlphaSift gặp lỗi khi truy cập dữ liệu thị trường hoặc dịch vụ mô hình, vui lòng thử lại sau hoặc kiểm tra cấu hình mạng/proxy.',
      rawMessage,
      status,
      category: 'upstream_network',
    });
  }

  const noConfiguredLlm = (
    includesAny(matchText, ['all llm models failed']) && includesAny(matchText, ['last error: none'])
  ) || includesAny(matchText, [
    'no llm configured',
    'no effective primary model configured',
    'litellm_model not configured',
    'ai analysis will be unavailable',
  ]);
  if (noConfiguredLlm) {
    return createParsedApiError({
      title: 'Chưa cấu hình mô hình LLM',
      message: 'Vui lòng cấu hình mô hình chính, kênh khả dụng hoặc API Key trong cài đặt hệ thống trước khi thử lại.',
      rawMessage,
      status,
      category: 'llm_not_configured',
    });
  }

  if (includesAny(matchText, [
    'tool call',
    'function call',
    'does not support tools',
    'tools is not supported',
    'reasoning',
  ])) {
    return createParsedApiError({
      title: 'Mô hình hiện tại không hỗ trợ tool call',
      message: 'Mô hình này không phù hợp với Agent / tool call, vui lòng chuyển sang mô hình hỗ trợ tool call rồi thử lại.',
      rawMessage,
      status,
      category: 'model_tool_incompatible',
    });
  }

  if (includesAny(matchText, [
    'thought_signature',
    'missing function',
    'missing tool',
    'invalid tool call',
    'invalid function call',
  ])) {
    return createParsedApiError({
      title: 'Cấu trúc phản hồi từ mô hình không hợp lệ',
      message: 'Mô hình trả về cấu trúc tool call không đúng yêu cầu, vui lòng đổi mô hình hoặc tắt chế độ suy luận rồi thử lại.',
      rawMessage,
      status,
      category: 'invalid_tool_call',
    });
  }

  if (includesAny(matchText, ['timeout', 'timed out', 'read timeout', 'connect timeout']) || code === 'ECONNABORTED') {
    return createParsedApiError({
      title: 'Kết nối đến dịch vụ ngoài bị timeout',
      message: 'Backend truy cập phụ thuộc ngoài bị timeout, vui lòng thử lại sau hoặc kiểm tra cấu hình mạng/proxy.',
      rawMessage,
      status,
      category: 'upstream_timeout',
    });
  }

  if (
    status === 502
    || status === 503
    || includesAny(matchText, [
      'dns',
      'enotfound',
      'name or service not known',
      'temporary failure in name resolution',
      'proxy',
      'tunnel',
      '502',
      '503',
    ])
  ) {
    return createParsedApiError({
      title: 'Backend không thể kết nối đến dịch vụ ngoài',
      message: 'Trang đã kết nối được đến dịch vụ cục bộ, nhưng dịch vụ cục bộ không thể truy cập mô hình hoặc API dữ liệu ngoài. Vui lòng kiểm tra proxy, DNS hoặc cấu hình mạng.',
      rawMessage,
      status,
      category: 'upstream_network',
    });
  }

  const hasLlmProviderHint = includesAny(matchText, [
    'chat/completions',
    'generativelanguage',
    'openai',
    'gemini',
  ]);
  if (status === 400 && hasLlmProviderHint) {
    return createParsedApiError({
      title: 'API mô hình từ chối yêu cầu',
      message: 'Dịch vụ cục bộ hoạt động bình thường, nhưng API mô hình từ chối yêu cầu. Vui lòng kiểm tra tên mô hình, định dạng tham số hoặc khả năng tương thích tool call.',
      rawMessage,
      status,
      category: 'upstream_llm_400',
    });
  }

  const localConnectionFailed = !response && (
    includesAny(matchText, ['fetch failed', 'failed to fetch', 'network error', 'connection refused', 'econnrefused'])
    || code === 'ERR_NETWORK'
    || code === 'ECONNREFUSED'
  );
  if (localConnectionFailed) {
    return createParsedApiError({
      title: 'Không thể kết nối đến dịch vụ cục bộ',
      message: 'Trình duyệt không thể kết nối đến Web service cục bộ. Vui lòng kiểm tra service đã khởi động chưa, địa chỉ lắng nghe và cổng có đúng không.',
      rawMessage,
      status,
      category: 'local_connection_failed',
    });
  }

  if (payloadText || status) {
    return createParsedApiError({
      title: 'Yêu cầu thất bại',
      message: payloadText ?? `Yêu cầu không thành công (HTTP ${status}).`,
      rawMessage,
      status,
      category: 'http_error',
    });
  }

  return createParsedApiError({
    title: 'Yêu cầu thất bại',
    message: rawMessage,
    rawMessage,
    status,
    category: 'unknown',
  });
}

export function toApiErrorMessage(error: unknown, fallback = 'Yêu cầu không thành công, vui lòng thử lại sau.'): string {
  const parsed = getParsedApiError(error);
  const message = formatParsedApiError(parsed);
  return message.trim() || fallback;
}

export function isAxiosApiError(error: unknown): boolean {
  return axios.isAxiosError(error);
}
