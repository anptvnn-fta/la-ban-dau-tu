/**
 * Các hàm tiện ích chuẩn hóa truy vấn
 *
 * Dùng để xử lý đầu vào của người dùng (mã cổ phiếu hoặc tên)
 */

/**
 * Chuẩn hóa chuỗi truy vấn
 * - Xóa khoảng trắng đầu/cuối
 * - Chuyển thành chữ thường
 * - Xóa khoảng trắng thừa bên trong
 */
export function normalizeQuery(query: string): string {
  return query
    .normalize('NFKC')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '');
}

/**
 * Kiểm tra ký tự có phải tiếng Trung không
 */
export function isChineseChar(char: string): boolean {
  return /[一-龥]/.test(char);
}

/**
 * Kiểm tra chuỗi có chứa ký tự tiếng Trung không
 */
export function containsChinese(query: string): boolean {
  return Array.from(query).some(isChineseChar);
}

/**
 * Trích xuất hậu tố thị trường từ mã cổ phiếu
 * Ví dụ: 600519.SH -> SH, 00700.HK -> HK
 */
export function extractMarketSuffix(code: string): string | null {
  const match = code.match(/\.([A-Z]+)$/);
  return match ? match[1] : null;
}

/**
 * Xóa hậu tố thị trường khỏi mã cổ phiếu
 * Ví dụ: 600519.SH -> 600519, 00700.HK -> 00700
 */
export function removeMarketSuffix(code: string): string {
  return code.replace(/\.[A-Z]+$/, '');
}

/**
 * Chuẩn hóa mã cổ phiếu
 * - Chuyển thành chữ hoa
 * - Xóa khoảng trắng
 * - Giữ nguyên hậu tố thị trường
 */
export function normalizeStockCode(code: string): string {
  return code.trim().toUpperCase().replace(/\s+/g, '');
}

/**
 * Kiểm tra truy vấn có giống mã cổ phiếu không
 * Dựa trên việc phát hiện số hoặc tổ hợp chữ cái
 */
export function isStockCodeLike(query: string): boolean {
  const normalized = normalizeQuery(query);
  // Có chứa số và không có tiếng Trung → có thể là mã cổ phiếu
  return /\d/.test(normalized) && !containsChinese(normalized);
}

/**
 * Kiểm tra truy vấn có giống tên cổ phiếu không
 * Dựa trên việc phát hiện tiếng Trung
 */
export function isStockNameLike(query: string): boolean {
  return containsChinese(query);
}

/**
 * Kiểm tra truy vấn có giống pinyin không
 * Dựa trên việc phát hiện chỉ có chữ cái và không có tiếng Trung
 */
export function isPinyinLike(query: string): boolean {
  const normalized = normalizeQuery(query);
  return /^[a-z]+$/.test(normalized) && !containsChinese(query);
}
