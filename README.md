<div align="center">

# 🧭 La Bàn Đầu Tư

**Hỗ trợ thông tin đầu tư bằng AI — đa kênh cho thị trường Việt Nam**

Cổ phiếu · Vàng · Xăng dầu · Tiết kiệm · Trái phiếu — phân tích & tư vấn bằng AI (LiteLLM) + dữ liệu vnstock

</div>

---

## Giới thiệu

**La Bàn Đầu Tư** là một nền tảng **hỗ trợ đầu tư đa kênh** dành riêng cho thị trường Việt Nam — không chỉ chứng khoán. Hệ thống giúp nhà đầu tư cá nhân theo dõi toàn cảnh các kênh đầu tư, phân tích cổ phiếu chuyên sâu, và nhận **gợi ý phân bổ danh mục theo hồ sơ rủi ro** — tất cả **100% tiếng Việt**.

- **Mô hình AI qua LiteLLM** làm bộ não phân tích & diễn giải — mặc định **Google Gemini**, nhưng có thể đổi sang **OpenAI**, **Anthropic** hay endpoint tương thích chỉ bằng cấu hình (xem [Chọn nhà cung cấp AI](#chọn-nhà-cung-cấp-ai)).
- **vnstock** + các nguồn công khai (SJC/BTMC, CafeF, yfinance…) làm dữ liệu giá cổ phiếu, vàng, xăng dầu, lãi suất, trái phiếu.
- Mọi nguồn dữ liệu đều **fail-open** (thiếu nguồn nào thì ẩn phần đó, phần còn lại vẫn chạy).

Dự án xây dựng lại trên nền engine đã kiểm chứng của `daily_stock_analysis`, tinh gọn, Việt hoá hoàn toàn và mở rộng thành hệ thống đầu tư đầy đủ.

## Tính năng chính

### 📊 Thị trường — toàn cảnh đầu tư
- **Tổng Quan**: VN-Index / VN30 / HNX / UPCOM, độ rộng, nhóm ngành, top tăng/giảm — kèm dải tóm tắt **các kênh đầu tư khác** (vàng, xăng dầu, tiết kiệm, trái phiếu).
- **Vàng**: giá SJC trong nước, giá thế giới quy đổi và **chênh lệch (premium)**, kèm lịch sử.
- **Xăng Dầu**: giá RON95 / E5 / E10 / dầu DO trong nước + dầu thế giới (Brent/WTI) + kỳ điều hành kế.
- **Tiết Kiệm**: lãi suất gửi của ~28 ngân hàng theo kỳ hạn + lãi suất điều hành SBV.
- **Trái Phiếu**: lợi suất TPCP Mỹ 10 năm, lãi suất điều hành SBV/Fed, mức tham khảo VN10Y.

### 🧠 Phân tích & Tư vấn
- **Phân Tích Cổ Phiếu**: nhận định kỹ thuật + cơ bản + khối ngoại + tin tức, kèm khuyến nghị và mốc giao dịch.
- **Tư Vấn Đầu Tư**: bảng hỏi hồ sơ **26 trường** (nhân khẩu / tài chính / hành vi) → chấm điểm **2 thang Khả năng vs Khẩu vị** (nguyên tắc thận trọng) → **phân bổ đa kênh** (tiết kiệm / trái phiếu / cổ phiếu / vàng) + danh sách cổ phiếu theo rổ biến động + **AI phân tích chân dung khách hàng** (chỉ diễn giải, không bịa số).
- **Trợ Lý AI**: hỏi đáp đa lượt, trả lời được **mọi kênh** — cổ phiếu, vàng, lãi suất tiết kiệm, trái phiếu, giá xăng dầu, danh mục.

### 💼 Đầu tư của tôi
- **Danh Mục**: theo dõi cổ phiếu **và** tài sản khác (vàng / tiết kiệm / trái phiếu), kèm **biểu đồ phân bổ tài sản** + tổng tài sản ròng.
- **Tín Hiệu AI**, **Đánh Giá Dự Báo** (kiểm thử lùi), **Cảnh Báo** (Telegram/Email), **Sử Dụng** (token AI), **Cài Đặt**.

> ⚖️ Mọi gợi ý mang tính **tham khảo**, không phải lời khuyên đầu tư chính thức. Con số phân bổ do **luật** quyết định; AI chỉ diễn giải.

## Cài đặt nhanh

```bash
# 1) Tạo môi trường & cài thư viện
pip install -r requirements.txt

# 2) Cấu hình
cp .env.example .env        # rồi điền khoá AI (mặc định GEMINI_API_KEY)

# 3) Chạy máy chủ web (chỉ phục vụ, không tự lên lịch)
python main.py --serve-only --host 127.0.0.1 --port 8000
# Mở http://127.0.0.1:8000
```

Frontend (thư mục `web/`):

```bash
cd web
npm install
npm run dev        # phát triển (proxy /api → :8000)
npm run build      # đóng gói ra ../static để FastAPI phục vụ
```

## Chọn nhà cung cấp AI

Hệ thống gọi mô hình qua **[LiteLLM](https://github.com/BerriAI/litellm)** nên **không khoá cứng vào một hãng**. Mặc định là **Google Gemini** (miễn phí, dễ lấy khoá), nhưng bạn có thể dùng nhà cung cấp khác chỉ bằng cách đổi `LITELLM_MODEL` + điền khoá tương ứng trong `.env`:

| Nhà cung cấp | `LITELLM_MODEL` (ví dụ) | Biến khoá trong `.env` |
|---|---|---|
| Google Gemini *(mặc định)* | `gemini/gemini-2.5-flash` | `GEMINI_API_KEY` |
| OpenAI | `openai/gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-3-5-haiku-latest` | `ANTHROPIC_API_KEY` |
| Endpoint tương thích OpenAI *(self-host, OpenRouter…)* | `openai/<tên-model>` | `OPENAI_API_KEY` + `OPENAI_BASE_URL` |

> Có thể đổi ngay trong trang **Cài Đặt** (ghi vào `.env`) mà không cần sửa file tay. Mọi mô hình LiteLLM hỗ trợ đều dùng được — chỉ cần đặt đúng tiền tố nhà cung cấp ở `LITELLM_MODEL`.

## Kiến trúc

| Tầng | Vị trí | Vai trò |
|---|---|---|
| Backend (Python/FastAPI) | `api/`, `src/`, `data_provider/` | Engine phân tích, pipeline, agent đa kênh, dữ liệu vnstock |
| Dịch vụ đa tài sản | `src/services/{gold,petrol,savings,bond,tu_van}_service.py` | Lấy & tổng hợp dữ liệu vàng/xăng/tiết kiệm/trái phiếu + chấm điểm hồ sơ rủi ro |
| Frontend (React/Vite) | `web/` | Giao diện tiếng Việt (thiết kế mới, điều hướng theo nhóm) |
| Dữ liệu | `data/` (SQLite) | Lịch sử phân tích, danh mục (gồm tài sản khác), cảnh báo |

> Mã nguồn gốc tiếng Trung đã được Việt hoá phần lớn (chuỗi người dùng thấy + comment) — không ảnh hưởng vận hành.

## Triển khai bằng Docker

Yêu cầu: Docker + Docker Compose. Chạy các lệnh từ **gốc dự án**.

```bash
# 1) Tạo .env với khóa AI (bắt buộc; mặc định Gemini)
cp .env.example .env        # điền khoá AI + chọn LITELLM_MODEL nếu dùng hãng khác

# 2) Build + chạy web/API (cổng 8000)
docker compose -f docker/docker-compose.yml up -d --build server
# Mở http://localhost:8000

# 3) (Tùy chọn) Bật chạy phân tích theo lịch
docker compose -f docker/docker-compose.yml up -d analyzer
```

Chi tiết:

- **Image đa tầng**: tầng Node build frontend `web/` → `static/`, tầng Python chạy FastAPI và phục vụ luôn `static/`.
- **Dữ liệu bền vững**: thư mục `data/` (SQLite), `logs/`, `reports/` được mount qua volume — nâng cấp image không mất dữ liệu.
- **Múi giờ**: `Asia/Ho_Chi_Minh` (UTC+7), khớp giờ giao dịch và lịch chạy tự động.
- **Cấu hình**: nạp từ `.env`; có thể chỉnh trực tiếp trong trang **Cài Đặt** (ghi vào `.env`).
- **Đổi cổng**: đặt `API_PORT` trong `.env`.

> **Khối ngoại, chỉ báo TA nâng cao và tin tức** dùng các gói mở rộng `vnstock_data` / `vnstock_ta` / `vnstock_news` (gói sponsor, cài qua `vnstock-installer`). Image mặc định chỉ có `vnstock` core; thiếu các gói này thì những tính năng trên tự ẩn (fail-open), phần còn lại vẫn chạy bình thường.

## Nguồn gốc & Giấy phép

**La Bàn Đầu Tư** được xây dựng lại trên nền dự án mã nguồn mở
[`daily_stock_analysis`](https://github.com/ZhuLinsen/daily_stock_analysis) của **ZhuLinsen** —
giữ lại engine phân tích đã kiểm chứng, đồng thời tinh gọn, Việt hoá toàn bộ và thiết kế lại giao
diện cho riêng thị trường Việt Nam. Xin chân thành cảm ơn tác giả gốc.

Dự án phát hành theo **giấy phép MIT** (xem [LICENSE](LICENSE)):

- Bản quyền tác phẩm gốc thuộc về **ZhuLinsen** (`daily_stock_analysis`).
- Phần chuyển ngữ & thích ứng cho thị trường Việt Nam thuộc về dự án **La Bàn Đầu Tư**.
- Khi tái sử dụng, vui lòng **giữ nguyên thông báo bản quyền + giấy phép** theo yêu cầu của MIT.
