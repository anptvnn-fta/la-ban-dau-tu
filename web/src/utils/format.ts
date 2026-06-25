export const formatDateTime = (value?: string | null): string => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat('vi-VN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

export const formatDate = (value?: string): string => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat('vi-VN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
};

export const toDateInputValue = (date: Date): string => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
};

/**
 * Trả về ngày N ngày trước theo định dạng YYYY-MM-DD, múi giờ Asia/Ho_Chi_Minh.
 */
export const getRecentStartDate = (days: number): string => {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(date);
};

/**
 * Trả về ngày hôm nay theo định dạng YYYY-MM-DD, múi giờ Asia/Ho_Chi_Minh.
 */
export const getTodayInHoChiMinh = (): string =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date());

/** Alias giữ tương thích với code cũ dùng getTodayInShanghai */
export const getTodayInShanghai = getTodayInHoChiMinh;

export const formatReportType = (value?: string): string => {
  if (!value) return '—';
  if (value === 'simple') return 'Thường';
  if (value === 'detailed') return 'Tiêu chuẩn';
  if (value === 'full') return 'Đầy đủ';
  if (value === 'brief') return 'Tóm tắt';
  if (value === 'market_review') return 'Thị trường';
  return value;
};
