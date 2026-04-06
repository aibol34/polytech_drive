#!/usr/bin/env bash
# На сервере (root): прокси /polytech_drive/ → gunicorn, include во все server aspc (в т.ч. HTTPS).
# Без этого nginx отдаёт SPA (try_files → index.html) вместо JSON API.
#
#   TARGET=/var/www/polytech_drive bash deploy/fix-nginx-polytech.sh
set -euo pipefail

TARGET="${TARGET:-/var/www/polytech_drive}"

echo "==> Сниппет /etc/nginx/snippets/polytech_drive.conf"
mkdir -p /etc/nginx/snippets
cat > /etc/nginx/snippets/polytech_drive.conf << 'LOC'
location ^~ /polytech_drive/ {
    proxy_pass http://127.0.0.1:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
    client_max_body_size 50m;
}
LOC

echo "==> Вставка include в конфиги nginx (sites-enabled + conf.d)"
python3 "$TARGET/deploy/nginx_add_include.py"

echo "==> Проверка backend (должен быть JSON)"
if curl -fsS "http://127.0.0.1:8010/polytech_drive/api/v1/health" 2>/dev/null | grep -q '"ok"'; then
  echo "gunicorn OK"
else
  echo "[!] gunicorn не отвечает JSON на 8010 — запустите: systemctl restart polytech-drive"
  echo "    или: bash $TARGET/deploy/bootstrap-server.sh"
fi

if systemctl cat polytech-drive.service >/dev/null 2>&1; then
  systemctl restart polytech-drive || true
fi

echo ""
echo "Проверьте в браузере: https://aspc.kz/polytech_drive/api/v1/health"
echo ""
echo "Если снаружи по-прежнему HTML/404 и заголовок X-Powered-By: Express —"
echo "домен обслуживает Node, а не этот nginx. См. deploy/OPENRESTY_OR_EXPRESS.txt"
