#!/usr/bin/env bash
# Запуск на сервере (bash): bash /var/www/polytech_drive/deploy/verify-server.sh
# Показывает, где сломано: gunicorn, nginx или Express/прокси.
set -uo pipefail

echo "=== 1. Gunicorn (должен быть JSON с ok:true) ==="
if curl -fsS --max-time 3 "http://127.0.0.1:8010/polytech_drive/api/v1/health" 2>/dev/null | grep -q '"ok"'; then
  echo "OK: 127.0.0.1:8010 отвечает"
else
  echo "FAIL: нет ответа от polytech на 8010. Выполните:"
  echo "  cd /var/www/polytech_drive && bash deploy/bootstrap-server.sh"
  echo "  systemctl status polytech-drive"
fi

echo ""
echo "=== 2. Снаружи (должен быть 200 и JSON) ==="
code=$(curl -fsS -o /tmp/polytech_health.json -w "%{http_code}" --max-time 10 "https://aspc.kz/polytech_drive/api/v1/health" 2>/dev/null || echo "000")
echo "HTTP $code"
if [[ "$code" == "200" ]] && grep -q '"ok"' /tmp/polytech_health.json 2>/dev/null; then
  echo "OK: домен проксирует на Flask"
else
  echo "FAIL: до Flask не доходит (часто Express/OpenResty без location)."
  head -c 200 /tmp/polytech_health.json 2>/dev/null | tr '\n' ' ' || true
  echo ""
  echo "Исправление: deploy/OPENRESTY_OR_EXPRESS.txt или поддомен в deploy/subdomain-drive.example.conf"
fi

echo ""
echo "=== 3. Заголовки ответа (ищем Express) ==="
curl -fsSI --max-time 10 "https://aspc.kz/polytech_drive/api/v1/health" 2>/dev/null | head -12 || true
