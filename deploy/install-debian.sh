#!/usr/bin/env bash
# Запуск от root на Debian: развёртывание в /var/www/polytech_drive
set -euo pipefail

TARGET="${TARGET:-/var/www/polytech_drive}"
REPO="${REPO:-https://github.com/aibol34/polytech_drive.git}"

mkdir -p "$(dirname "$TARGET")"
if [[ ! -d "$TARGET/.git" ]]; then
  git clone "$REPO" "$TARGET"
else
  git -C "$TARGET" pull --ff-only
fi

cd "$TARGET"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip wheel
pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Создан $TARGET/.env — отредактируйте SECRET_KEY, GOOGLE_DRIVE_API_KEY, APPLICATION_ROOT, PUBLIC_BASE_URL"
fi

echo "Дальше:"
echo "  1) nano $TARGET/.env"
echo "  2) sudo cp deploy/polytech-drive.service.example /etc/systemd/system/polytech-drive.service"
echo "  3) sudo systemctl daemon-reload && sudo systemctl enable --now polytech-drive"
echo "  4) Добавьте в nginx фрагмент из deploy/nginx-location-polytech_drive.conf.example и nginx -t && systemctl reload nginx"
