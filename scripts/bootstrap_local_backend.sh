#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ "$ENV_FILE" == ".env" ]]; then
    cp .env.example .env
    echo "Created .env from .env.example. Update secrets before non-local use."
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

if grep -Eq "replace-with|change-me" "$ENV_FILE"; then
  echo "Warning: '$ENV_FILE' still contains placeholder secrets."
fi

"${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" up -d --build
"${COMPOSE_CMD[@]}" ps

echo
echo "Backend stack started."
SERVER_HOST="${SERVER_HOST:-localhost}"
echo "Health endpoint: https://${SERVER_HOST}/v1/health"
