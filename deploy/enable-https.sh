#!/usr/bin/env bash
# HTTPS (Let's Encrypt) для aspc.kz + обновление .env и polytech в nginx.
# Запуск на сервере от root:
#   export CERTBOT_EMAIL="ваш@email.com"
#   bash /var/www/polytech_drive/deploy/enable-https.sh
set -euo pipefail

TARGET="${TARGET:-/var/www/polytech_drive}"
PREFIX="${PREFIX:-/polytech_drive}"
EMAIL="${CERTBOT_EMAIL:-}"

if [[ -z "$EMAIL" ]]; then
  echo "Задайте email для Let's Encrypt, например:"
  echo "  export CERTBOT_EMAIL=admin@aspc.kz"
  echo "  bash $TARGET/deploy/enable-https.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y certbot python3-certbot-nginx

echo "==> Certbot (нужны DNS A на этот сервер и открыты 80/443)"
certbot --nginx \
  -d aspc.kz \
  -d www.aspc.kz \
  --non-interactive --agree-tos \
  --email "$EMAIL" \
  --redirect

echo "==> Сниппет polytech (если ещё нет)"
mkdir -p /etc/nginx/snippets
if [[ ! -f /etc/nginx/snippets/polytech_drive.conf ]]; then
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
fi

echo "==> include в каждый server с aspc (в т.ч. после certbot)"
python3 "$TARGET/deploy/nginx_add_include.py" || {
  echo "Добавьте вручную в server { } для HTTPS:"
  echo "    include /etc/nginx/snippets/polytech_drive.conf;"
}

cd "$TARGET"
set_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i "s#^${key}=.*#${key}=${val}#" .env
  else
    echo "${key}=${val}" >> .env
  fi
}
set_kv "PUBLIC_BASE_URL" "https://aspc.kz${PREFIX}"
set_kv "USE_HTTPS" "true"

nginx -t
systemctl reload nginx

if systemctl cat polytech-drive.service >/dev/null 2>&1; then
  systemctl restart polytech-drive
else
  echo "[!] Сервис polytech-drive не найден. После настройки приложения:"
  echo "    bash $TARGET/deploy/bootstrap-server.sh"
fi

echo ""
echo "Готово. Проверьте: https://aspc.kz${PREFIX}/api/v1/health"
echo "Админка: https://aspc.kz${PREFIX}/admin"
