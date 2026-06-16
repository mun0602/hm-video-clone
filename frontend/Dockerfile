# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files và install dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Định nghĩa các biến môi trường build-time cho Supabase Mock URL (Backend FastAPI)
ARG REACT_APP_SUPABASE_URL
ENV REACT_APP_SUPABASE_URL=$REACT_APP_SUPABASE_URL
ENV REACT_APP_SUPABASE_KEY=mock-key-for-fastapi
ENV REACT_APP_ENVIRONMENT=production

# Build ứng dụng
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy code đã build sang thư mục của Nginx
COPY --from=builder /app/build /usr/share/nginx/html

# Copy file cấu hình nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
