const { override, addWebpackAlias } = require('customize-cra');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (config, env) {
  // 1) Webpack alias cho '~' -> src/
  const aliasOverride = override(
    addWebpackAlias({
      '~': path.resolve(__dirname, 'src'),
    }),
  );
  config = aliasOverride(config, env);

  // 2) Proxy /static và /uploads -> FastAPI backend (port 8000)
  // Cần thiết vì video URL trong DB là relative (/static/uploads/videos/...)
  // mà React dev server catch-all trả SPA index.html thay vì file MP4 thật.
  if (env === 'development') {
    const staticProxy = createProxyMiddleware('/static', {
      target: 'http://localhost:8000',
      changeOrigin: true,
      logLevel: 'debug',
    });
    const uploadsProxy = createProxyMiddleware('/uploads', {
      target: 'http://localhost:8000',
      changeOrigin: true,
    });
    // webpack-dev-server v4 dùng onBeforeSetupMiddleware
    config.devServer = config.devServer || {};
    config.devServer.onBeforeSetupMiddleware = (devServer) => {
      devServer.app.use(staticProxy);
      devServer.app.use(uploadsProxy);
    };
  }

  return config;
};
