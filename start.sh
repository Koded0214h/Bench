#!/usr/bin/env bash
# Bring Bench up: build the frontend, migrate, seed policy, make a demo user,
# smoke-test Solari, then start the server. Open http://localhost:8000/app/
set -euo pipefail
cd "$(dirname "$0")"

export DJANGO_SETTINGS_MODULE="bench.control_plane.settings"
if [ -f .env ]; then set -a; . ./.env; set +a; fi

: "${SOLARI_API_KEY:?SOLARI_API_KEY is required (put it in .env)}"

if [ ! -d frontend/dist ]; then
  echo "▸ build frontend"
  ( cd frontend && npm install && npm run build )
fi

echo "▸ migrations";            python manage.py migrate --noinput
echo "▸ seed default policy";   python manage.py seed_policy
echo "▸ demo user";             python manage.py seed_demo
echo "▸ Solari smoke test";     python manage.py smoke

echo
echo "starting the server — open  http://localhost:8000/app/"
echo "(demo login: ${BENCH_DEMO_USER:-demo} / ${BENCH_DEMO_PASSWORD:-bench-demo-pass})"
exec python manage.py runserver "${BENCH_HOST:-127.0.0.1}:${BENCH_PORT:-8000}"
