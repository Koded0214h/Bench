#!/usr/bin/env bash
# Bring the Bench control plane up: migrate, seed policy, provision a JWT, and
# smoke-test Solari. Then start the API server.
set -euo pipefail
cd "$(dirname "$0")"

export DJANGO_SETTINGS_MODULE="bench.control_plane.settings"

if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

: "${SOLARI_API_KEY:?SOLARI_API_KEY is required (put it in .env)}"

echo "▸ migrations"
python manage.py migrate --noinput

echo "▸ seed default policy set"
python manage.py seed_policy

echo "▸ provision JWT"
python manage.py provision_token --username bench --print

echo "▸ Solari smoke test"
python manage.py smoke

echo
echo "ready. start the API with:"
echo "    python manage.py runserver 0.0.0.0:8000"
echo "then open  http://localhost:8000/live"
