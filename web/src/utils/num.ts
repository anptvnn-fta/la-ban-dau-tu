// Định dạng số kiểu Việt Nam (vi-VN).

const VN = 'vi-VN'

/** Số nguyên/thập phân với dấu phân tách hàng nghìn. */
export function fmtNum(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return new Intl.NumberFormat(VN, { minimumFractionDigits: 0, maximumFractionDigits: digits }).format(value)
}

/** Giá cổ phiếu (VND), không hiển thị ký hiệu tiền để gọn bảng. */
export function fmtPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return new Intl.NumberFormat(VN, { maximumFractionDigits: value >= 1000 ? 0 : 2 }).format(value)
}

/** Phần trăm thay đổi, kèm dấu +/-. */
export function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  const sign = value > 0 ? '+' : ''
  return `${sign}${new Intl.NumberFormat(VN, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)}%`
}

/** Rút gọn số lớn: 1.2K, 3.4M, 1.1 tỷ. */
export function fmtCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  const abs = Math.abs(value)
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)} tỷ`
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)} tr`
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}K`
  return fmtNum(value, 0)
}

/** Lớp màu theo chiều giá (xanh tăng / đỏ giảm / trung tính). */
export function priceToneClass(changePct: number | null | undefined): string {
  if (changePct === null || changePct === undefined || changePct === 0) return 'text-flat'
  return changePct > 0 ? 'text-up' : 'text-down'
}
