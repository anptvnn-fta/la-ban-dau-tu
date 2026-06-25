<div align="center">

# 📈 StockViet AI

**Phân tích cổ phiếu Việt Nam thông minh — bằng AI (Google Gemini) + dữ liệu vnstock**

</div>

---

## Giới thiệu

**StockViet AI** là hệ thống phân tích chứng khoán dành riêng cho thị trường Việt Nam (HOSE / HNX / UPCOM). Hệ thống dùng:

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
