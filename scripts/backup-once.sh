#!/usr/bin/env bash
# Runs inside the PostgreSQL backup service. Row counts and dump use ONE snapshot.
set -euo pipefail
umask 077
directory=${BACKUP_DIRECTORY:-/backups}
retention=${BACKUP_RETENTION_COUNT:-7}
[[ "$retention" =~ ^[0-9]+$ && "$retention" -ge 2 ]] || exit 2
mkdir -p "$directory"
work=$(mktemp -d /tmp/radar-backup.XXXXXXXX)
name="radar-$(date -u +%Y%m%dT%H%M%SZ)-$$"
archive="$directory/$name.dump"
session_pid=''
cleanup() {
  exec 7>&- 2>/dev/null || true
  if [[ -n "$session_pid" ]]; then
    kill "$session_pid" 2>/dev/null || true
    wait "$session_pid" 2>/dev/null || true
  fi
  rm -rf -- "$work"
}
trap cleanup EXIT
mkfifo "$work/input"
psql -X -A -t -q --set=ON_ERROR_STOP=1 < "$work/input" > "$work/session.log" 2>&1 &
session_pid=$!
exec 7>"$work/input"
# Closing each \o output flushes its file while the transaction stays open.
cat >&7 <<SQL
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
\o $work/snapshot
SELECT pg_export_snapshot();
\o $work/counts
SELECT format('SELECT %L || ''|'' || count(*) FROM %I.%I;', tablename, schemaname, tablename)
FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename
\gexec
\o $work/ready
SELECT 'ready';
\o
SQL
ready=0
for ((attempt=0; attempt<300; attempt++)); do
  if [[ -s "$work/ready" ]]; then ready=1; break; fi
  if ! kill -0 "$session_pid" 2>/dev/null; then break; fi
  sleep 0.1
done
if [[ "$ready" != 1 ]]; then
  cat "$work/session.log" >&2
  echo 'Cannot acquire a consistent backup snapshot.' >&2
  exit 1
fi
snapshot=$(head -n 1 "$work/snapshot")
[[ "$snapshot" =~ ^[A-Fa-f0-9-]+$ ]] || { echo 'Invalid PostgreSQL snapshot.' >&2; exit 1; }
pg_dump --format=custom --no-owner --no-acl --snapshot="$snapshot" --file="$work/archive.dump"
pg_restore --list "$work/archive.dump" >/dev/null
[[ -s "$work/counts" ]] || { echo 'Backup has no public tables; migrations must run first.' >&2; exit 1; }
printf 'ROLLBACK;\n\\q\n' >&7
exec 7>&-
wait "$session_pid"
session_pid=''
mv "$work/counts" "$directory/$name.counts"
mv "$work/archive.dump" "$archive"
(cd "$directory" && sha256sum "$name.dump" "$name.counts" > "$work/checksums")
mv "$work/checksums" "$directory/$name.sha256"
# Prune ONLY complete archives after a validated new archive exists.
mapfile -t archives < <(find "$directory" -maxdepth 1 -type f -name 'radar-*.sha256' -printf '%f\n' | sort -r)
for ((index=retention; index<${#archives[@]}; index++)); do
  old=${archives[index]%.sha256}
  rm -f -- "$directory/$old.dump" "$directory/$old.counts" "$directory/$old.sha256"
done
echo "$(date -u +%FT%TZ) created $name.dump with consistent table counts; retention=$retention"
