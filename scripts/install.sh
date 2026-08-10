#!/usr/bin/env sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Engine or Docker Desktop, then rerun this script." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required. Install the docker compose plugin, then rerun this script." >&2
  exit 1
fi

docker compose build

echo "Install complete. Start the app with: ./scripts/deploy.sh"
