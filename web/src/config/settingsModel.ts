// ============================================================
//  Mô hình trang Cài Đặt — bản "curated" cho sản phẩm VN dùng Gemini.
//
//  Thay vì đổ ~120 trường thô (kèm mô tả dịch máy) vào một danh sách,
//  ta CHỌN LỌC đúng những gì người dùng VN cần, chia thành các đề mục con
//  rõ ràng, mỗi trường có nhãn + lời giải thích tiếng Việt gần gũi, dễ hiểu.
//
//  Mọi text ở đây là tiếng Việt thuần — không rò rỉ Trung/Anh (đồng nhất với
//  nguyên tắc của strings/vi.ts). Các trường KHÔNG có ở đây vẫn nằm yên trong
//  .env, chỉ là không hiển thị để trang gọn gàng.
// ============================================================

import type { LucideIcon } from 'lucide-react'
import {
  Sparkles, FileText, Star, Clock, Bell, Activity, SlidersHorizontal,
} from 'lucide-react'

export type SettingControl = 'text' | 'password' | 'switch' | 'select' | 'number' | 'textarea' | 'time'

export interface SettingField {
  /** Khóa env trùng với config_registry (vd GEMINI_API_KEY). */
  key: string
  /** Nhãn tiếng Việt thân thiện (đè lên title của schema). */
  label: string
  /** Lời giải thích ngắn gọn, dễ hiểu (đè lên description của schema). */
  help?: string
  /** Gợi ý nhập trong ô. */
  placeholder?: string
  /** Kiểu điều khiển; nếu bỏ trống sẽ suy ra từ schema. */
  control?: SettingControl
  /** Lựa chọn cho select (đè lên options của schema). */
  options?: { label: string; value: string }[]
  /** Đánh dấu là trường bắt buộc (chỉ để hiện dấu *). */
  required?: boolean
}

/** Widget hành động đặc biệt gắn vào cuối một nhóm. */
export type SettingAction = 'test-telegram' | 'test-email' | 'scheduler-run'

export interface SettingGroup {
  id: string
  title: string
  /** Một câu dẫn dắt ngắn cho nhóm. */
  intro?: string
  /** Nhóm nâng cao → mặc định thu gọn. */
  advanced?: boolean
  fields: SettingField[]
  /** Widget hành động (nút gửi thử, chạy ngay…). */
  action?: SettingAction
}

export interface SettingSection {
  id: string
  title: string
  icon: LucideIcon
  /** Câu mô tả mục đích của đề mục, hiện ngay dưới tiêu đề. */
  blurb: string
  groups: SettingGroup[]
  /** Cả đề mục là nâng cao → mặc định thu gọn. */
  collapsed?: boolean
  /** Gợi ý/ghi chú cuối đề mục (vd link sang trang khác). */
  note?: 'alert-rules'
}

export const SETTINGS_SECTIONS: SettingSection[] = [
  // ── 1. Trí tuệ AI ─────────────────────────────────────────
  {
    id: 'ai',
    title: 'Trí tuệ AI',
    icon: Sparkles,
    blurb: 'Gemini của Google là bộ não chính. Bạn có thể thêm các nguồn AI khác (OpenAI, Claude, DeepSeek) làm dự phòng khi cần.',
    groups: [
      {
        id: 'gemini',
        title: 'Gemini (nguồn chính)',
        intro: 'La Bàn Đầu Tư cần một khóa API để gọi Gemini. Bạn có thể lấy miễn phí tại Google AI Studio.',
        fields: [
          {
            key: 'GEMINI_API_KEY',
            label: 'Khóa API Gemini',
            help: 'Dán khóa bắt đầu bằng “AIza…”. Lấy tại aistudio.google.com/apikey.',
            control: 'password',
            required: true,
          },
          {
            key: 'LITELLM_MODEL',
            label: 'Mô hình phân tích chính',
            help: 'Mặc định gemini/gemini-2.5-flash — nhanh và tiết kiệm. Đổi mô hình ở đây là đổi luôn nhà cung cấp: ví dụ gemini/gemini-2.5-pro, openai/gpt-4o-mini hay anthropic/claude-3-5-haiku-latest (nhớ điền khoá tương ứng bên dưới).',
            placeholder: 'gemini/gemini-2.5-flash',
            control: 'text',
          },
        ],
      },
      {
        id: 'ai-advanced',
        title: 'Tinh chỉnh chung',
        intro: 'Để mặc định nếu bạn không chắc.',
        advanced: true,
        fields: [
          {
            key: 'LITELLM_FALLBACK_MODELS',
            label: 'Mô hình dự phòng',
            help: 'Khi nguồn chính lỗi hoặc hết hạn mức, hệ thống tự chuyển sang các mô hình này (cần điền API key tương ứng ở các mục bên dưới). Nhiều mô hình cách nhau dấu phẩy.',
            placeholder: 'openai/gpt-4o-mini, deepseek/deepseek-chat',
            control: 'text',
          },
          {
            key: 'LLM_TEMPERATURE',
            label: 'Độ sáng tạo',
            help: '0 = bám sát dữ liệu, 1 = bay bổng hơn. Phân tích tài chính nên để thấp (0 – 0.4).',
            placeholder: '0.3',
            control: 'number',
          },
          {
            key: 'AGENT_LITELLM_MODEL',
            label: 'Mô hình cho Trợ Lý AI',
            help: 'Để trống = dùng chung mô hình phân tích chính ở trên.',
            placeholder: 'gemini/gemini-2.5-flash',
            control: 'text',
          },
        ],
      },
      {
        id: 'openai',
        title: 'OpenAI (tùy chọn)',
        intro: 'Chỉ điền nếu bạn có khóa OpenAI và muốn dùng làm nguồn dự phòng. Nhớ thêm “openai/<mô hình>” vào ô Mô hình dự phòng ở trên để kích hoạt.',
        advanced: true,
        fields: [
          {
            key: 'OPENAI_API_KEY',
            label: 'Khóa API OpenAI',
            help: 'Chuỗi bắt đầu bằng “sk-…” từ platform.openai.com.',
            control: 'password',
          },
          {
            key: 'OPENAI_MODEL',
            label: 'Mô hình OpenAI',
            help: 'Ví dụ gpt-4o-mini.',
            placeholder: 'gpt-4o-mini',
            control: 'text',
          },
          {
            key: 'OPENAI_BASE_URL',
            label: 'Base URL (tùy chọn)',
            help: 'Để trống nếu dùng OpenAI chính thức. Điền nếu dùng một cổng tương thích OpenAI.',
            placeholder: 'https://api.openai.com/v1',
            control: 'text',
          },
        ],
      },
      {
        id: 'anthropic',
        title: 'Anthropic · Claude (tùy chọn)',
        intro: 'Chỉ điền nếu bạn có khóa Anthropic. Thêm “anthropic/<mô hình>” vào ô Mô hình dự phòng để kích hoạt.',
        advanced: true,
        fields: [
          {
            key: 'ANTHROPIC_API_KEY',
            label: 'Khóa API Anthropic',
            help: 'Chuỗi bắt đầu bằng “sk-ant-…” từ console.anthropic.com.',
            control: 'password',
          },
          {
            key: 'ANTHROPIC_MODEL',
            label: 'Mô hình Claude',
            help: 'Ví dụ claude-sonnet-4-5.',
            placeholder: 'claude-sonnet-4-5',
            control: 'text',
          },
        ],
      },
      {
        id: 'deepseek',
        title: 'DeepSeek (tùy chọn)',
        intro: 'Chỉ điền nếu bạn có khóa DeepSeek. Thêm “deepseek/deepseek-chat” vào ô Mô hình dự phòng để kích hoạt.',
        advanced: true,
        fields: [
          {
            key: 'DEEPSEEK_API_KEY',
            label: 'Khóa API DeepSeek',
            help: 'Lấy tại platform.deepseek.com.',
            control: 'password',
          },
        ],
      },
    ],
  },

  // ── 2. Báo cáo & Thị trường ───────────────────────────────
  {
    id: 'report',
    title: 'Báo cáo & Thị trường',
    icon: FileText,
    blurb: 'Ngôn ngữ báo cáo và phần điểm lại diễn biến thị trường mỗi ngày.',
    groups: [
      {
        id: 'report-basic',
        title: 'Báo cáo',
        fields: [
          {
            key: 'REPORT_LANGUAGE',
            label: 'Ngôn ngữ báo cáo',
            help: 'Để “Tiếng Việt” cho toàn bộ báo cáo và thông báo bằng tiếng Việt.',
            control: 'select',
            options: [
              { label: 'Tiếng Việt', value: 'vi' },
              { label: 'English', value: 'en' },
              { label: '中文', value: 'zh' },
            ],
          },
          {
            key: 'REPORT_SUMMARY_ONLY',
            label: 'Chỉ gửi bản tóm tắt',
            help: 'Bật để báo cáo gọn lại, chỉ giữ phần kết luận và khuyến nghị.',
            control: 'switch',
          },
        ],
      },
      {
        id: 'market-review',
        title: 'Điểm lại thị trường',
        fields: [
          {
            key: 'MARKET_REVIEW_ENABLED',
            label: 'Tự động điểm lại thị trường',
            help: 'Tạo bản tổng quan VN-Index, dòng tiền và nhóm ngành sau mỗi phiên.',
            control: 'switch',
          },
        ],
      },
    ],
  },

  // ── 3. Danh mục theo dõi ──────────────────────────────────
  {
    id: 'watchlist',
    title: 'Danh mục theo dõi',
    icon: Star,
    blurb: 'Những mã cổ phiếu được phân tích tự động và dùng cho cảnh báo.',
    groups: [
      {
        id: 'watchlist-list',
        title: 'Danh sách mã',
        fields: [
          {
            key: 'STOCK_LIST',
            label: 'Mã cổ phiếu theo dõi',
            help: 'Mỗi mã cách nhau bởi dấu phẩy. Nhớ thêm đuôi .VN — ví dụ: FPT.VN, VCB.VN, HPG.VN.',
            placeholder: 'FPT.VN, VCB.VN, HPG.VN',
            control: 'textarea',
          },
        ],
      },
    ],
  },

  // ── 4. Lịch tự động (U2) ──────────────────────────────────
  {
    id: 'schedule',
    title: 'Lịch tự động',
    icon: Clock,
    blurb: 'Hẹn giờ để La Bàn Đầu Tư tự phân tích danh mục mỗi ngày — bạn chỉ việc đọc kết quả.',
    groups: [
      {
        id: 'schedule-basic',
        title: 'Chạy theo lịch',
        fields: [
          {
            key: 'SCHEDULE_ENABLED',
            label: 'Bật chạy tự động hằng ngày',
            help: 'Khi bật, hệ thống tự phân tích toàn bộ danh mục vào giờ bên dưới.',
            control: 'switch',
          },
          {
            key: 'SCHEDULE_TIME',
            label: 'Giờ chạy mỗi ngày',
            help: 'Định dạng 24 giờ. Nên đặt sau khi thị trường đóng cửa, ví dụ 18:00.',
            placeholder: '18:00',
            control: 'time',
          },
          {
            key: 'TRADING_DAY_CHECK_ENABLED',
            label: 'Chỉ chạy vào ngày giao dịch',
            help: 'Tự bỏ qua thứ Bảy, Chủ nhật và ngày nghỉ lễ.',
            control: 'switch',
          },
        ],
        action: 'scheduler-run',
      },
      {
        id: 'schedule-advanced',
        title: 'Nhiều mốc giờ',
        advanced: true,
        fields: [
          {
            key: 'SCHEDULE_TIMES',
            label: 'Các mốc giờ',
            help: 'Nhiều giờ cách nhau dấu phẩy, ví dụ 09:30, 14:00. Để trống nếu chỉ cần một mốc ở trên.',
            placeholder: '09:30, 14:00',
            control: 'text',
          },
        ],
      },
    ],
  },

  // ── 5. Thông báo (U2) ─────────────────────────────────────
  {
    id: 'notify',
    title: 'Thông báo',
    icon: Bell,
    blurb: 'Nhận báo cáo và cảnh báo gửi thẳng về Telegram hoặc Email của bạn.',
    groups: [
      {
        id: 'telegram',
        title: 'Telegram',
        intro: 'Tạo bot qua @BotFather để lấy token, rồi lấy Chat ID của bạn.',
        fields: [
          {
            key: 'TELEGRAM_BOT_TOKEN',
            label: 'Token bot',
            help: 'Chuỗi dạng 123456:ABC… do @BotFather cấp.',
            control: 'password',
          },
          {
            key: 'TELEGRAM_CHAT_ID',
            label: 'Chat ID',
            help: 'ID đoạn chat nhận tin. Nhắn @userinfobot để biết ID của bạn.',
            control: 'text',
          },
        ],
        action: 'test-telegram',
      },
      {
        id: 'email',
        title: 'Email',
        intro: 'Dùng email kèm “mật khẩu ứng dụng” (App Password), không phải mật khẩu đăng nhập thường.',
        fields: [
          {
            key: 'EMAIL_SENDER',
            label: 'Email gửi đi',
            help: 'Địa chỉ dùng để gửi báo cáo, ví dụ ban@gmail.com.',
            placeholder: 'ban@gmail.com',
            control: 'text',
          },
          {
            key: 'EMAIL_PASSWORD',
            label: 'Mật khẩu ứng dụng',
            help: 'Với Gmail: bật xác thực 2 bước rồi tạo “App Password” 16 ký tự.',
            control: 'password',
          },
          {
            key: 'EMAIL_RECEIVERS',
            label: 'Email nhận',
            help: 'Nơi nhận báo cáo. Nhiều địa chỉ cách nhau dấu phẩy.',
            placeholder: 'toi@gmail.com, nguoikhac@gmail.com',
            control: 'text',
          },
        ],
        action: 'test-email',
      },
      {
        id: 'routing',
        title: 'Định tuyến',
        intro: 'Chọn kênh nào nhận loại tin nào. Để trống = gửi tới mọi kênh đã cấu hình.',
        advanced: true,
        fields: [
          {
            key: 'NOTIFICATION_REPORT_CHANNELS',
            label: 'Kênh nhận báo cáo',
            help: 'Ví dụ: telegram,email.',
            placeholder: 'telegram,email',
            control: 'text',
          },
          {
            key: 'NOTIFICATION_ALERT_CHANNELS',
            label: 'Kênh nhận cảnh báo',
            help: 'Ví dụ: telegram.',
            placeholder: 'telegram',
            control: 'text',
          },
        ],
      },
    ],
  },

  // ── 6. Cảnh báo thông minh (U2) ───────────────────────────
  {
    id: 'alerts',
    title: 'Cảnh báo thông minh',
    icon: Activity,
    blurb: 'Hệ thống tự theo dõi điều kiện giá/kỹ thuật và báo ngay khi cổ phiếu chạm ngưỡng bạn đặt.',
    note: 'alert-rules',
    groups: [
      {
        id: 'monitor',
        title: 'Giám sát',
        fields: [
          {
            key: 'AGENT_EVENT_MONITOR_ENABLED',
            label: 'Bật giám sát cảnh báo',
            help: 'Khi bật, hệ thống định kỳ kiểm tra các quy tắc cảnh báo và gửi thông báo khi đạt điều kiện.',
            control: 'switch',
          },
          {
            key: 'AGENT_EVENT_MONITOR_INTERVAL_MINUTES',
            label: 'Kiểm tra mỗi (phút)',
            help: 'Khoảng thời gian giữa hai lần quét. Mặc định 5 phút.',
            placeholder: '5',
            control: 'number',
          },
        ],
      },
    ],
  },

  // ── 7. Hệ thống (nâng cao) ────────────────────────────────
  {
    id: 'system',
    title: 'Hệ thống',
    icon: SlidersHorizontal,
    blurb: 'Tùy chọn kỹ thuật. Để mặc định nếu bạn không chắc.',
    collapsed: true,
    groups: [
      {
        id: 'system-basic',
        title: 'Vận hành',
        fields: [
          {
            key: 'MAX_WORKERS',
            label: 'Số luồng phân tích song song',
            help: 'Nhiều luồng chạy nhanh hơn nhưng tốn tài nguyên hơn.',
            placeholder: '4',
            control: 'number',
          },
          {
            key: 'ANALYSIS_DELAY',
            label: 'Nghỉ giữa các mã (giây)',
            help: 'Giãn cách mỗi lần gọi để tránh bị nhà cung cấp dữ liệu chặn.',
            placeholder: '2',
            control: 'number',
          },
          {
            key: 'LOG_LEVEL',
            label: 'Mức ghi log',
            help: 'INFO là đủ dùng. DEBUG để xem chi tiết khi gỡ lỗi.',
            control: 'select',
            options: [
              { label: 'INFO', value: 'INFO' },
              { label: 'DEBUG', value: 'DEBUG' },
              { label: 'WARNING', value: 'WARNING' },
              { label: 'ERROR', value: 'ERROR' },
              { label: 'CRITICAL', value: 'CRITICAL' },
            ],
          },
          {
            key: 'DEBUG',
            label: 'Chế độ gỡ lỗi',
            help: 'Bật để ghi thêm thông tin chẩn đoán. Nên tắt khi dùng bình thường.',
            control: 'switch',
          },
        ],
      },
    ],
  },
]

/** Tập hợp mọi khóa được trang Cài Đặt curated dùng tới — để tải/giá trị/đối chiếu. */
export const SETTINGS_KEYS: string[] = SETTINGS_SECTIONS.flatMap((s) =>
  s.groups.flatMap((g) => g.fields.map((f) => f.key)),
)
