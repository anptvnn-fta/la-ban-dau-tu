<div align="center">

# 📈 La Bàn Đầu Tư

**Phân tích cổ phiếu Việt Nam thông minh — bằng AI (Google Gemini) + dữ liệu vnstock**

</div>

---

## Giới thiệu

**La Bàn Đầu Tư** là hệ thống phân tích chứng khoán dành riêng cho thị trường Việt Nam (HOSE / HNX / UPCOM). Hệ thống dùng:

- **Google Gemini** (qua LiteLLM) làm bộ não phân tích.
- **vnstock** làm nguồn dữ liệu giá, cơ bản, chỉ số kỹ thuật và tin tức.
- Báo cáo & giao diện **100% tiếng Việt**.

Dự án được xây dựng lại trên nền engine đã kiểm chứng của `daily_stock_analysis`, tinh gọn và Việt hoá hoàn toàn cho người dùng Việt.

## Tính năng chính

- **Phân tích cổ phiếu**: nhận định kỹ thuật + cơ bản + khối ngoại + tin tức, kèm khuyến nghị và mốc giao dịch.
- **Diễn biến thị trường**: tổng kết VN-Index / VN30 / HNX-Index / UPCOM-Index bằng tiếng Việt.
- **Trợ lý AI**: hỏi đáp đa lượt về cổ phiếu.
- **Danh mục, Tín hiệu AI, Đánh giá dự báo, Cảnh báo** và nhiều hơn nữa.

## Cài đặt nhanh

```bash
# 1) Tạo môi trường & cài thư viện
pip install -r requirements.txt

# 2) Cấu hình
cp .env.example .env        # rồi điền GEMINI_API_KEY

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

## Kiến trúc

| Tầng | Vị trí | Vai trò |
|---|---|---|
| Backend (Python/FastAPI) | `api/`, `src/`, `data_provider/` | Engine phân tích, pipeline, agent, dữ liệu vnstock |
| Frontend (React/Vite) | `web/` | Giao diện tiếng Việt (thiết kế mới) |
| Dữ liệu | `data/` (SQLite) | Lịch sử phân tích, danh mục, cảnh báo |

> Mã nguồn gốc tiếng Trung đang được Việt hoá dần (comment/docstring) — không ảnh hưởng vận hành.

## Triển khai bằng Docker

Yêu cầu: Docker + Docker Compose. Chạy các lệnh từ **gốc dự án**.

```bash
# 1) Tạo .env với khóa Gemini (bắt buộc)
cp .env.example .env        # rồi điền GEMINI_API_KEY

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
