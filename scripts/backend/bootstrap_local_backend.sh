#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-config/env/local.env}"
COMPOSE_FILE="deploy/docker/docker-compose.yml"

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ "$ENV_FILE" == "config/env/local.env" ]]; then
    cp config/env/local.env.example config/env/local.env
    echo "Created config/env/local.env from config/env/local.env.example. Update secrets before non-local use."
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

PALEO_ENV_FILE="$ENV_FILE" "${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build
PALEO_ENV_FILE="$ENV_FILE" "${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

echo
echo "Backend stack started."
SERVER_HOST="${SERVER_HOST:-localhost}"
echo "Health endpoint: https://${SERVER_HOST}/v1/health"
