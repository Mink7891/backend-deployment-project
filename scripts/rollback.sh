#!/usr/bin/env bash
# Explicit image rollback; schema must remain compatible with the old application.
set -euo pipefail
cd "$(dirname "$0")/.."
tag=${1:-}
if [[ -z "$tag" ]]; then
  [[ -f .deploy/previous ]] || { echo 'No previous release recorded; supply its full commit SHA.' >&2; exit 2; }
  tag=$(cat .deploy/previous)
fi
bash scripts/deploy.sh "$tag" production
