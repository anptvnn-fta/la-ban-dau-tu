// ============================================================
//  StockViet AI — Toàn bộ chuỗi giao diện (tiếng Việt duy nhất)
//  KHÔNG có bộ i18n zh/en. Mọi text hiển thị nằm ở đây.
//  → Rò rỉ ngôn ngữ là bất khả thi về mặt cấu trúc.
// ============================================================

export const VI = {
  app: {
    name: 'StockViet AI',
    short: 'StockViet',
    tagline: 'Phân tích cổ phiếu Việt Nam thông minh',
  },

  nav: {
    home: 'Phân Tích',
    chat: 'Trợ Lý AI',
    portfolio: 'Danh Mục',
    signals: 'Tín Hiệu',
    backtest: 'Đánh Giá',
    screening: 'Lọc Cổ Phiếu',
    alerts: 'Cảnh Báo',
    usage: 'Sử Dụng',
    settings: 'Cài Đặt',
    logout: 'Đăng Xuất',
    theme: 'Giao diện',
    themeLight: 'Sáng',
    themeDark: 'Tối',
  },

  common: {
    analyze: 'Phân tích',
    reanalyze: 'Phân tích lại',
    search: 'Tìm kiếm',
    loading: 'Đang tải...',
    save: 'Lưu',
    cancel: 'Huỷ',
    delete: 'Xoá',
    confirm: 'Xác nhận',
    close: 'Đóng',
    retry: 'Thử lại',
    refresh: 'Làm mới',
    edit: 'Sửa',
    add: 'Thêm',
    remove: 'Bỏ',
    viewDetails: 'Xem chi tiết',
    copy: 'Sao chép',
    copied: 'Đã sao chép',
    noData: 'Chưa có dữ liệu',
    empty: 'Trống',
    all: 'Tất cả',
    open: 'Mở',
    back: 'Quay lại',
    next: 'Tiếp',
    prev: 'Trước',
    page: 'Trang',
    total: 'Tổng',
    yes: 'Có',
    no: 'Không',
    up: 'Tăng',
    down: 'Giảm',
    flat: 'Tham chiếu',
  },

  home: {
    title: 'Phân tích cổ phiếu',
    searchPlaceholder: 'Nhập mã hoặc tên cổ phiếu, ví dụ VCB, Vinamilk, FPT',
    analyzeBtn: 'Phân tích',
    marketReviewBtn: 'Diễn biến thị trường',
    sendNotify: 'Gửi thông báo',
    fullReport: 'Báo cáo đầy đủ',
    historyTrend: 'Xu hướng lịch sử',
    rerunMarketReview: 'Chạy lại diễn biến thị trường',
    stocks: 'Cổ phiếu',
    selectAll: 'Chọn tất cả',
    keyInsights: 'Nhận định chính',
    actionAdvice: 'Khuyến nghị hành động',
    trendPrediction: 'Dự báo xu hướng',
    marketSentiment: 'Tâm lý thị trường',
    strategyPoints: 'Mốc chiến lược',
    idealBuy: 'Điểm mua lý tưởng',
    secondaryBuy: 'Điểm mua bổ sung',
    stopLoss: 'Cắt lỗ',
    takeProfit: 'Chốt lời',
    relatedBoards: 'Nhóm ngành liên quan',
    news: 'Tin tức',
    emptyAnalysis: 'Nhập một mã cổ phiếu để bắt đầu phân tích.',
  },

  chat: {
    title: 'Trợ lý AI',
    placeholder: 'Hỏi về một cổ phiếu hoặc thị trường...',
    send: 'Gửi',
    newChat: 'Cuộc trò chuyện mới',
    sessions: 'Lịch sử trò chuyện',
    thinking: 'Đang suy nghĩ...',
    emptyState: 'Bắt đầu hỏi trợ lý AI về cổ phiếu Việt Nam.',
  },

  portfolio: {
    title: 'Danh mục đầu tư',
    account: 'Tài khoản',
    addAccount: 'Thêm tài khoản',
    holdings: 'Cổ phiếu nắm giữ',
    symbol: 'Mã',
    quantity: 'Số lượng',
    avgPrice: 'Giá vốn',
    marketPrice: 'Giá thị trường',
    marketValue: 'Giá trị',
    pnl: 'Lãi/Lỗ',
    weight: 'Tỷ trọng',
    risk: 'Phân tích rủi ro',
    trades: 'Giao dịch',
    emptyState: 'Chưa có tài khoản. Hãy tạo một tài khoản để theo dõi danh mục.',
  },

  signals: {
    title: 'Tín hiệu AI',
    action: 'Hành động',
    confidence: 'Độ tin cậy',
    score: 'Điểm',
    horizon: 'Khung thời gian',
    entry: 'Vùng mua',
    stopLoss: 'Cắt lỗ',
    target: 'Mục tiêu',
    risk: 'Rủi ro',
    catalyst: 'Chất xúc tác',
    status: 'Trạng thái',
    emptyState: 'Chưa có tín hiệu. Tín hiệu được trích từ các báo cáo phân tích.',
  },

  backtest: {
    title: 'Đánh giá dự báo',
    subtitle: 'Đo độ chính xác của dự báo AI so với giá thực tế',
    run: 'Chạy đánh giá',
    results: 'Kết quả',
    accuracy: 'Độ chính xác',
    window: 'Cửa sổ đánh giá (ngày)',
    emptyState: 'Chạy đánh giá để xem độ chính xác của các dự báo trước đây.',
  },

  alerts: {
    title: 'Cảnh báo',
    rules: 'Quy tắc cảnh báo',
    addRule: 'Thêm quy tắc',
    triggers: 'Lịch sử kích hoạt',
    type: 'Loại',
    target: 'Đối tượng',
    severity: 'Mức độ',
    enabled: 'Bật',
    emptyState: 'Chưa có quy tắc cảnh báo nào.',
  },

  usage: {
    title: 'Sử dụng AI',
    today: 'Hôm nay',
    month: 'Tháng này',
    allTime: 'Tất cả',
    totalCalls: 'Tổng lượt gọi',
    totalTokens: 'Tổng token',
    byModel: 'Theo mô hình',
    byCallType: 'Theo loại tác vụ',
    recentCalls: 'Lượt gọi gần đây',
  },

  settings: {
    title: 'Cài đặt',
    save: 'Lưu thay đổi',
    saved: 'Đã lưu',
    llmChannels: 'Kênh LLM',
    notification: 'Thông báo',
    auth: 'Bảo mật',
    scheduler: 'Lịch chạy',
    testNotify: 'Gửi thử thông báo',
  },

  auth: {
    login: 'Đăng nhập',
    password: 'Mật khẩu',
    passwordConfirm: 'Xác nhận mật khẩu',
    loginBtn: 'Đăng nhập',
    wrongPassword: 'Mật khẩu không đúng',
    setupTitle: 'Thiết lập lần đầu',
  },

  errors: {
    generic: 'Đã xảy ra lỗi. Vui lòng thử lại.',
    network: 'Mất kết nối tới máy chủ.',
    notFound: 'Không tìm thấy.',
    marketReviewInProgress: 'Diễn biến thị trường đang chạy, vui lòng thử lại sau.',
    provideFileOrText: 'Vui lòng cung cấp tệp hoặc dán văn bản.',
    invalidStockCode: 'Vui lòng nhập mã hoặc tên cổ phiếu hợp lệ.',
  },

  toast: {
    analysisQueued: 'Đã đưa vào hàng đợi phân tích',
    analysisDone: 'Phân tích hoàn tất',
    marketReviewQueued: 'Đã gửi tác vụ diễn biến thị trường',
    saved: 'Đã lưu',
    deleted: 'Đã xoá',
    copied: 'Đã sao chép',
  },

  notFound: {
    title: 'Không tìm thấy trang',
    backHome: 'Về trang chủ',
  },
} as const

/** Thay tham số trong chuỗi mẫu: vif('Tổng {n} kết quả', { n: 5 }). */
export const vif = (template: string, vars: Record<string, string | number>): string =>
  template.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ''))

export type ViStrings = typeof VI
