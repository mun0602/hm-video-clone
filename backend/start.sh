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
  # Sao chép trực tiếp nội dung các thư mục con để tránh cp -rn bỏ qua khi thư mục cha đã tồn tại
  cp -rn /app/static_backup/uploads/thumbnails/. /app/static/uploads/thumbnails/
  cp -rn /app/static_backup/uploads/videos/. /app/static/uploads/videos/
  cp -n /app/static_backup/uploads/* /app/static/uploads/ 2>/dev/null || true
  echo "Đã khôi phục xong các file demo."
fi

# Chạy uvicorn server
exec uvicorn main:app --host 0.0.0.0 --port 8000
