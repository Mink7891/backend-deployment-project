#!/usr/bin/env bash
# Restore the newest (or named) archive into an isolated DB; never overwrite production.
set -euo pipefail
cd "$(dirname "$0")/.."
compose_file=${COMPOSE_FILE:-docker-compose.deploy.yml}
project=${COMPOSE_PROJECT_NAME:-game-radar}
env_file=${ENV_FILE:-.env}
archive=${1:-latest}
[[ "$archive" == latest || "$archive" =~ ^radar-[0-9TZ-]+\.dump$ ]] || { echo 'Supply an archive basename, or latest.' >&2; exit 2; }
docker compose --env-file "$env_file" -p "$project" -f "$compose_file" --profile operations \
  exec -T backup bash /opt/backup/restore-in-container.sh "$archive"
