# ===================================
# La Bàn Đầu Tư — Docker image
# ===================================
# Multi-stage: build frontend (Node) rồi chạy backend FastAPI + phục vụ static.

FROM node:20-slim AS web-builder

WORKDIR /app/web

# Cài dependencies trước (tận dụng cache layer)
COPY web/package.json web/package-lock.json ./
RUN npm ci

# Build frontend → Vite ghi ra /app/static (theo vite.config.ts: outDir '../static')
COPY web/ ./
RUN npm run build

# Pin bookworm: wkhtmltopdf đã bị gỡ khỏi Debian testing (2025)
FROM python:3.11-slim-bookworm

WORKDIR /app

# Múi giờ Việt Nam (UTC+7) — khớp giờ giao dịch và lịch chạy tự động
ENV TZ=Asia/Ho_Chi_Minh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Thư viện hệ thống (wkhtmltopdf để xuất báo cáo ảnh; git để cài gói từ git URL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    git \
    gosu \
    wkhtmltopdf \
    fontconfig \
    libjpeg62-turbo \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Người dùng không phải root (UID 1000)
RUN groupadd -g 1000 dsa && \
    useradd -u 1000 -g dsa -m dsa

# Cài Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Mã ứng dụng
COPY *.py ./
COPY api/ ./api/
COPY data_provider/ ./data_provider/
COPY bot/ ./bot/
COPY src/ ./src/
COPY strategies/ ./strategies/
COPY --from=web-builder /app/static ./static/
COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# AlphaSift (bộ lọc CN tuỳ chọn) — không bắt buộc cho thị trường VN; không chặn build nếu thiếu
RUN python -c "import alphasift.dsa_adapter" 2>/dev/null || \
    echo "[build] AlphaSift không khả dụng (bỏ qua — không cần cho VN)"

# Thư mục dữ liệu + phân quyền cho user dsa
RUN mkdir -p /app/data /app/logs /app/reports && \
    chown -R dsa:dsa /app && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

# efinance ghi cache vào thư mục cài đặt của chính nó (mặc định thuộc root) — cấp quyền
# cho dsa để tránh PermissionError. Không chặn build nếu efinance không có.
RUN EF_DATA_DIR="$(python -c 'import efinance, pathlib; print(pathlib.Path(efinance.__file__).parent / "data")' 2>/dev/null)" && \
    if [ -n "$EF_DATA_DIR" ]; then mkdir -p "$EF_DATA_DIR" && chown -R dsa:dsa "$EF_DATA_DIR"; fi || true

# Biến môi trường mặc định
ENV PYTHONUNBUFFERED=1
ENV LOG_DIR=/app/logs
ENV DATABASE_PATH=/app/data/stock_analysis.db
ENV WEBUI_HOST=0.0.0.0
ENV API_PORT=8000
# Mặc định sản phẩm VN
ENV MARKET_REVIEW_REGION=vn
ENV REPORT_LANGUAGE=vi

EXPOSE 8000

# Ổ đĩa dữ liệu (lưu trữ bền vững)
VOLUME ["/app/data", "/app/logs", "/app/reports"]

# Kiểm tra sức khoẻ (chế độ FastAPI)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || curl -f http://localhost:8000/health \
    || python -c "import sys; sys.exit(1)"

# Entrypoint sửa quyền thư mục bind-mount rồi hạ quyền xuống dsa
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Mặc định: chạy server web + API (có thể ghi đè bằng --schedule để chạy theo lịch)
CMD ["python", "main.py", "--serve-only", "--host", "0.0.0.0", "--port", "8000"]
