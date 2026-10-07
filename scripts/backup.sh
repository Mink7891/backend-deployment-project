#!/bin/sh
# Резервное копирование БД по расписанию: раз в сутки, хранятся 7 последних копий.
# Запускается в контейнере backup (docker-compose.yml).
set -eu

while true; do
    file="/backups/game_radar_$(date +%Y-%m-%d_%H-%M-%S).sql.gz"
    # --clean --if-exists: дамп сам удаляет старые объекты при восстановлении.
    if pg_dump --clean --if-exists --no-owner | gzip > "$file.tmp"; then
        mv "$file.tmp" "$file"
        echo "backup created: $file"
    else
        rm -f "$file.tmp"
        echo "backup failed" >&2
    fi
    ls -1t /backups/*.sql.gz 2>/dev/null | tail -n +8 | xargs -r rm -f
    sleep 86400
done
