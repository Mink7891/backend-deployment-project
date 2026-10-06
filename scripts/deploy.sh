#!/usr/bin/env bash
# Run on machine 2. Optional registry args read its password ONLY from stdin.
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
tag=${1:?Usage: deploy.sh COMMIT_TAG [production|load] [REGISTRY USERNAME]}
mode=${2:-production}
[[ "$tag" =~ ^[a-f0-9]{40,64}$ ]] || { echo 'Use a full Git commit SHA as image tag.' >&2; exit 2; }
[[ "$mode" == production || "$mode" == load ]] || exit 2
auth_directory=''
cleanup() { if [[ -n "$auth_directory" ]]; then rm -rf -- "$auth_directory"; fi; }
trap cleanup EXIT
if [[ -n "${3:-}" ]]; then
  auth_directory=$(mktemp -d /tmp/radar-registry.XXXXXXXX)
  export DOCKER_CONFIG="$auth_directory"
  docker login "$3" --username "${4:?Registry username is required}" --password-stdin >/dev/null
fi
export IMAGE_TAG="$tag"
if [[ "$mode" == load ]]; then
  compose=(docker compose --env-file .env.load -p game-radar-load -f docker-compose.deploy.yml -f docker-compose.load.yml --profile monitoring)
  # Only this fixed sandbox project owns these disposable volumes; production is separate.
  "${compose[@]}" down --volumes
  services=(db app worker postgres_exporter prometheus grafana)
  "${compose[@]}" pull "${services[@]}"
  "${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 240 "${services[@]}"
  echo "Isolated mock load deployment ready for commit $tag"
  exit 0
fi
compose=(docker compose --env-file .env -p game-radar -f docker-compose.deploy.yml --profile monitoring --profile operations)
mkdir -p .deploy
current=''
if [[ -f .deploy/current ]]; then current=$(cat .deploy/current); fi
# Back up the existing live DB BEFORE applying this version's migration.
if [[ -n "$current" ]]; then
  "${compose[@]}" exec -T backup bash /opt/backup/backup-once.sh
fi
"${compose[@]}" pull
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 240
if [[ -n "$current" && "$current" != "$tag" ]]; then printf '%s\n' "$current" > .deploy/previous; fi
printf '%s\n' "$tag" > .deploy/current
echo "Production deployment healthy at commit $tag"
