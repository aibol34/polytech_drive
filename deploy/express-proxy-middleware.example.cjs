/**
 * Пример для Express: проксировать /polytech_drive на gunicorn (Flask).
 * Установка: npm i http-proxy-middleware
 *
 * Вставить в server.js ПЕРЕД app.get('*', ...) / SPA fallback.
 */
const { createProxyMiddleware } = require("http-proxy-middleware");

// Путь /polytech_drive/... уходит на gunicorn как есть (PrefixMiddleware во Flask).
const polytechProxy = createProxyMiddleware({
  target: "http://127.0.0.1:8010",
  changeOrigin: true,
});

app.use("/polytech_drive", polytechProxy);
