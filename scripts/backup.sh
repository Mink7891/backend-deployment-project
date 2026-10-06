#!/usr/bin/env bash
# Host wrapper: use COMPOSE_FILE=docker-compose.yml for a local development stack.
set -euo pipefail
cd "$(dirname "$0")/.."
compose_file=${COMPOSE_FILE:-docker-compose.deploy.yml}
project=${COMPOSE_PROJECT_NAME:-game-radar}
env_file=${ENV_FILE:-.env}
docker compose --env-file "$env_file" -p "$project" -f "$compose_file" --profile operations \
  exec -T backup bash /opt/backup/backup-once.sh
