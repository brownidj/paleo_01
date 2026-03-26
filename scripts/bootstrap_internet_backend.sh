#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-config/env/prod.env}"
COMPOSE_FILE="deploy/docker/docker-compose.yml"
COMPOSE_FILE_INET="deploy/docker/docker-compose.internet.yml"

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ "$ENV_FILE" == "config/env/prod.env" ]]; then
    cp config/env/prod.env.example config/env/prod.env
    echo "Created config/env/prod.env from config/env/prod.env.example. Update domain, email, and secrets first."
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

PALEO_ENV_FILE="$ENV_FILE" "${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" -f "$COMPOSE_FILE_INET" up -d --build
PALEO_ENV_FILE="$ENV_FILE" "${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" -f "$COMPOSE_FILE_INET" ps

echo
echo "Internet-access backend stack started."
echo "Health endpoint: https://${SERVER_HOST:-unset}/v1/health"
