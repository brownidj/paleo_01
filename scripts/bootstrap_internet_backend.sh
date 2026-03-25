#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env.prod}"

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ "$ENV_FILE" == ".env.prod" ]]; then
    cp .env.prod.example .env.prod
    echo "Created .env.prod from .env.prod.example. Update domain, email, and secrets first."
  else
    echo "ENV_FILE '$ENV_FILE' not found." >&2
    exit 1
  fi
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Neither 'docker compose' nor 'docker-compose' is available." >&2
  exit 1
fi

if grep -Eq "replace-with|change-me|example.com" "$ENV_FILE"; then
  echo "Warning: '$ENV_FILE' still contains placeholder values."
fi

"${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.internet.yml up -d --build
"${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.internet.yml ps

echo
echo "Internet-access backend stack started."
echo "Health endpoint: https://${SERVER_HOST:-unset}/v1/health"
