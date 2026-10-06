#!/usr/bin/env bash
set -eu
[[ -r /tmp/backup-success ]] || exit 1
last=$(cat /tmp/backup-success)
now=$(date +%s)
[[ "$last" =~ ^[0-9]+$ ]] || exit 1
(( now - last <= ${BACKUP_INTERVAL_SECONDS:-86400} * 2 ))
