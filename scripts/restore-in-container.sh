#!/usr/bin/env bash
set -euo pipefail
umask 077
directory=${BACKUP_DIRECTORY:-/backups}
archive=${1:-latest}
if [[ "$archive" == latest ]]; then
  archive=$(find "$directory" -maxdepth 1 -type f -name 'radar-*.sha256' -printf '%f\n' | sort -r | head -n 1)
  archive="${archive%.sha256}.dump"
fi
[[ "$archive" =~ ^radar-[0-9TZ-]+\.dump$ ]] || { echo 'No valid backup archive found.' >&2; exit 2; }
stem=${archive%.dump}
[[ -f "$directory/$stem.sha256" && -f "$directory/$stem.counts" ]] || { echo 'Incomplete backup archive.' >&2; exit 1; }
(cd "$directory" && sha256sum --check "$stem.sha256")
database="radar_restore_$(date +%s)_$$"
work=$(mktemp -d /tmp/radar-restore.XXXXXXXX)
created=0
cleanup() {
  if [[ "$created" == 1 ]]; then dropdb --if-exists "$database" || true; fi
  rm -rf -- "$work"
}
trap cleanup EXIT
createdb "$database"
created=1
pg_restore --exit-on-error --no-owner --no-acl --dbname="$database" "$directory/$archive"
psql -X -A -t -q --dbname="$database" --set=ON_ERROR_STOP=1 > "$work/counts" <<'SQL'
SELECT format('SELECT %L || ''|'' || count(*) FROM %I.%I;', tablename, schemaname, tablename)
FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename
\gexec
SQL
diff -u "$directory/$stem.counts" "$work/counts"
version=$(psql -X -A -t -q --dbname="$database" --set=ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')
[[ -n "$version" ]] || { echo 'Missing restored migration version.' >&2; exit 1; }
echo "Restore verified in $database; every table count matches the dump snapshot; migration=$version"
cat "$work/counts"
echo 'The temporary verification database is removed on exit; the live database was untouched.'
