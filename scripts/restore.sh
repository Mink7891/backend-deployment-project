#!/bin/sh
# Восстановление БД из резервной копии.
# Использование (на машине деплоя, в каталоге проекта):
#   docker compose exec backup sh /scripts/restore.sh                 # последняя копия
#   docker compose exec backup sh /scripts/restore.sh /backups/<файл> # конкретная копия
set -eu

file="${1:-$(ls -1t /backups/*.sql.gz | head -n 1)}"
echo "restoring from: $file"
gunzip -c "$file" | psql --quiet --set ON_ERROR_STOP=1
echo "restore finished"
