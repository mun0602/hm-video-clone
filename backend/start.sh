#!/bin/sh
mkdir -p /app/data
if [ ! -f /app/data/tiktok.db ]; then
  echo "Cơ sở dữ liệu sqlite không tìm thấy trong volume, đang sao chép cơ sở dữ liệu mặc định..."
  if [ -f /app/tiktok.db ]; then
    cp /app/tiktok.db /app/data/tiktok.db
  fi
fi
# Chạy uvicorn server
exec uvicorn main:app --host 0.0.0.0 --port 8000
