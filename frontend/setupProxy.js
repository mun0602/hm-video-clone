// Proxy config: forward /static/* và /uploads/* từ port 3000 sang port 8000 (FastAPI).
// Cần thiết vì React dev server (Express) catch-all trả SPA HTML cho mọi URL.
// File này được CRA tự động load (đặt tại src/ hoặc root với tên setupProxy.js).

const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  // Forward static files + uploads tới FastAPI backend
  app.use(
    '/static',
    createProxyMiddleware({
      target: 'http://localhost:8000',
      changeOrigin: true,
      // Range requests support để Chrome có thể seek video
      headers: {
        'X-Forwarded-Proto': 'http',
      },
    })
  );

  app.use(
    '/uploads',
    createProxyMiddleware({
      target: 'http://localhost:8000',
      changeOrigin: true,
    })
  );
};
