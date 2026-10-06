#!/usr/bin/env bash
set -eu
umask 077
interval=${BACKUP_INTERVAL_SECONDS:-86400}
retention=${BACKUP_RETENTION_COUNT:-7}
[[ "$interval" =~ ^[0-9]+$ && "$interval" -ge 60 ]] || { echo 'Backup interval must be >=60 seconds.' >&2; exit 2; }
[[ "$retention" =~ ^[0-9]+$ && "$retention" -ge 2 ]] || { echo 'Keep at least two backup archives.' >&2; exit 2; }
mkdir -p /backups
trap 'exit 0' TERM INT
while true; do
  if bash /opt/backup/backup-once.sh; then
    date +%s > /tmp/backup-success
    delay=$interval
  else
    rm -f /tmp/backup-success
    delay=60
    echo "$(date -u +%FT%TZ) backup failed; retry in ${delay}s" >&2
  fi
  sleep "$delay" &
  wait "$!" || true
done
