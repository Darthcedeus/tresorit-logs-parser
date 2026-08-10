#!/usr/bin/env sh
set -eu

APP_PORT="${APP_PORT:-5000}"
export APP_PORT

docker compose up -d --build

echo "Tresorit logs parser is running at http://localhost:${APP_PORT}"
echo "View logs with: docker compose logs -f"
