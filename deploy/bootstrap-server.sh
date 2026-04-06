#!/usr/bin/env bash
# Запуск на сервере от root: bash /var/www/polytech_drive/deploy/bootstrap-server.sh
# Или после клона: curl ... | bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
TARGET="${TARGET:-/var/www/polytech_drive}"
REPO="${REPO:-https://github.com/aibol34/polytech_drive.git}"
PUBLIC_URL="${PUBLIC_URL:-https://aspc.kz/polytech_drive}"
PREFIX="${PREFIX:-/polytech_drive}"

echo "==> Пакеты: nginx, git, python3, openssl"
apt-get update -qq
apt-get install -y nginx git python3 python3-venv python3-pip openssl curl

echo "==> Клон репозитория -> $TARGET"
mkdir -p "$(dirname "$TARGET")"
if [[ ! -d "$TARGET/.git" ]]; then
  git clone "$REPO" "$TARGET"
else
  git -C "$TARGET" pull --ff-only || true
fi

cd "$TARGET"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -U pip wheel
pip install -q -r requirements.txt

SECRET=$(openssl rand -hex 32)
if [[ ! -f .env ]]; then
  cp .env.example .env
fi

set_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i "s#^${key}=.*#${key}=${val}#" .env
  else
    echo "${key}=${val}" >> .env
  fi
}

set_kv "FLASK_ENV" "production"
set_kv "APPLICATION_ROOT" "$PREFIX"
set_kv "PUBLIC_BASE_URL" "$PUBLIC_URL"
set_kv "SECRET_KEY" "$SECRET"

mkdir -p instance
chown -R www-data:www-data "$TARGET"
chmod 750 instance
chmod 640 .env 2>/dev/null || chmod 600 .env

echo "==> systemd: polytech-drive"
cat > /etc/systemd/system/polytech-drive.service << 'UNIT'
[Unit]
Description=polytech_drive (Flask + gunicorn)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/polytech_drive
Environment=PATH=/var/www/polytech_drive/.venv/bin
Environment=FLASK_ENV=production
ExecStart=/var/www/polytech_drive/.venv/bin/gunicorn -w 2 -b 127.0.0.1:8010 --timeout 120 wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable polytech-drive
systemctl restart polytech-drive

echo "==> nginx: сниппет location"
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

echo "==> nginx: автопатч конфигов с server_name aspc"
if python3 "$TARGET/deploy/nginx_add_include.py"; then
  echo "nginx OK"
else
  echo "-------------------------------------------------------------------"
  echo "Вручную в server { } для aspc.kz добавьте:"
  echo "    include /etc/nginx/snippets/polytech_drive.conf;"
  echo "Затем: nginx -t && systemctl reload nginx"
  echo "-------------------------------------------------------------------"
fi

systemctl status polytech-drive --no-pager -l || true
echo ""
echo "Админка: ${PUBLIC_URL}/admin"
echo "API health: ${PUBLIC_URL}/api/v1/health"
echo "Не забудьте GOOGLE_DRIVE_API_KEY в $TARGET/.env"
