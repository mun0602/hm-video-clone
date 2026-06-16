#!/bin/sh
mkdir -p /app/data
if [ ! -f /app/data/tiktok.db ]; then
  echo "Cơ sở dữ liệu sqlite không tìm thấy trong volume, đang sao chép cơ sở dữ liệu mặc định..."
  if [ -f /app/tiktok.db ]; then
    cp /app/tiktok.db /app/data/tiktok.db
  fi
fi
# Tạo các thư mục lưu trữ tĩnh trong volume mount
mkdir -p /app/static/uploads/videos
mkdir -p /app/static/uploads/thumbnails

# Khôi phục các file tĩnh demo từ bản sao lưu nếu chúng chưa tồn tại trong volume mount
if [ -d /app/static_backup/uploads ]; then
  echo "Đang khôi phục các file media/video demo vào volume..."
  cp -rn /app/static_backup/uploads/* /app/static/uploads/
fi

# Chạy uvicorn server
exec uvicorn main:app --host 0.0.0.0 --port 8000
