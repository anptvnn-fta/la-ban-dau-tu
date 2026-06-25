/**
 * Định nghĩa hằng số trường chỉ mục cổ phiếu
 *
 * Dùng trong quá trình nén/giải nén dữ liệu chỉ mục
 */

export const STOCK_INDEX_FIELDS = [
  'canonicalCode',
  'displayCode',
  'nameZh',
  'pinyinFull',
  'pinyinAbbr',
  'aliases',
  'market',
  'assetType',
  'active',
  'popularity',
] as const;

/**
 * Chỉ số trường trong định dạng nén
 */
export const INDEX_FIELD = {
  CANONICAL_CODE: 0,
  DISPLAY_CODE: 1,
  NAME_ZH: 2,
  PINYIN_FULL: 3,
  PINYIN_ABBR: 4,
  ALIASES: 5,
  MARKET: 6,
  ASSET_TYPE: 7,
  ACTIVE: 8,
  POPULARITY: 9,
} as const;

/**
 * Ngưỡng điểm khớp
 */
export const MATCH_SCORE = {
  EXACT_MIN: 96,   // Điểm tối thiểu cho khớp chính xác
  PREFIX_MIN: 77,  // Điểm tối thiểu cho khớp tiền tố
  CONTAINS_MIN: 57, // Điểm tối thiểu cho khớp chứa
  FUZZY_MIN: 1,    // Điểm tối thiểu cho khớp mờ
} as const;

/**
 * Cấu hình tìm kiếm
 */
export const SEARCH_CONFIG = {
  DEFAULT_LIMIT: 10,      // Số kết quả trả về mặc định
  DEBOUNCE_MS: 200,       // Độ trễ debounce (mili giây)
  MIN_QUERY_LENGTH: 2,    // Độ dài truy vấn tối thiểu
  ACTIVE_ONLY: true,      // Chỉ hiển thị cổ phiếu đang hoạt động
} as const;
