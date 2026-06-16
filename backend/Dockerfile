FROM python:3.11-slim

# Cài đặt các package hệ thống cần thiết và ffmpeg để xử lý video
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements và install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code backend
COPY . .

# Sao lưu thư mục static gốc để phục hồi khi mount Docker volume
RUN cp -r /app/static /app/static_backup

# Expose cổng 8000
EXPOSE 8000

# Chạy startup script
CMD ["/app/start.sh"]
