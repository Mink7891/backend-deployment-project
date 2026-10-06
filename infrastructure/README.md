# Инфраструктура Game Radar

`docker-compose.yml` собирает приложение локально. Профиль `monitoring` добавляет
Prometheus, PostgreSQL Exporter и Grafana; `operations` — резервное копирование.
`docker-compose.deploy.yml` содержит только образы из реестров и никогда не
собирает приложение на машине деплоя.

## Две машины и Jenkins

На машине 1 работает Linux-агент Jenkins с меткой `linux-ci`: Git, Docker с Compose
V2, uv, Python 3.12, Trivy и Apache JMeter. Здесь выполняются линтер, автотесты,
сборка, сканирование, публикация образа и генерация нагрузки. Репозиторий должен
находиться на GitHub. Jenkins использует плагины Pipeline, Credentials Binding,
JUnit и Git. Для Linux shell-скриптов в репозитории закреплены окончания строк LF.

На машине 2 нужны Docker с Compose V2, Bash и SSH. Создайте каталог, например
`/opt/game-radar`, доступный пользователю деплоя. Этот пользователь должен иметь
доступ к Docker. Инструменты сборки и JMeter на машине 2 не требуются. Jenkins
проверяет, что адрес машины 2 отличается от адресов своего CI-агента.

Параметры Jenkins `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`, `IMAGE_REPOSITORY`
нужно заполнить своими значениями. Порты API 8000 и 8001 должны быть доступны
из сети CI-агента; файлы CI задают `APP_BIND_ADDRESS=0.0.0.0`. Ограничьте доступ
правилами выбранной частной сети. Prometheus и Grafana слушают только loopback.

Секреты создаются в Jenkins Credentials:

| ID | Тип и значение |
| --- | --- |
| `registry-auth` | Username with password: пользователь реестра и токен с правом push/pull |
| `deploy-ssh` | SSH Username with private key: ключ пользователя деплоя |
| `deploy-known-hosts` | Secret file: проверенный `known_hosts` машины 2 |
| `radar-api-key` | Secret text: общий учебный API-ключ не короче 16 символов |
| `postgres-password` | Secret text: пароль PostgreSQL |
| `grafana-password` | Secret text: пароль администратора Grafana |

CI создаёт временные env-файлы с правами 0600, передаёт их по SSH и удаляет локальные
копии. SSH проверяет ключ сервера через `known_hosts`. Пароли реестра поступают
через stdin; временный Docker config удаляется после pull/push. Env-файлы не
сохраняются в артефакты. Используйте случайные ASCII-ключи, например hex-токены.

## Отдельный стенд для нагрузки

`scripts/write_deploy_env.py` создаёт `.env` и `.env.load` из Jenkins Credentials.
Учебный production-стенд использует CheapShark. Песочница имеет фиксированное имя
Compose-проекта `game-radar-load`, собственную БД `radar_load`, собственные volumes,
API на порту 8001, Prometheus на 9091 и Grafana на 3001. Во время проверки оба
процесса, API и worker, принудительно используют `PRICE_SOURCE=mock`; условие
проверяется по `/health` перед запуском JMeter.

Песочница запускается после smoke-проверки production. JMeter на машине 1 создаёт
нагрузку на машину 2. После теста Jenkins экспортирует временные ряды Prometheus
в `reports/load-monitoring.json`, сохраняет HTML-отчёт JMeter и результат gate,
затем удаляет только контейнеры и volumes проекта `game-radar-load`. Production
остаётся в проекте `game-radar`. Тестовый стенд также очищается перед новым тестом.

Для доступа к временной Grafana во время теста используйте SSH-туннель:

```bash
ssh -L 3001:127.0.0.1:3001 deploy@MACHINE_2
```

Откройте `http://localhost:3001` и dashboard «Game Radar — API and PostgreSQL».
В обычной Grafana на порту 3000 отображаются метрики production-стенда.

## Резервное копирование и откат

Backup-контейнер создаёт первую копию после готовности схемы и повторяет действие
каждые `BACKUP_INTERVAL_SECONDS` (по умолчанию сутки). Хранятся последние
`BACKUP_RETENTION_COUNT` успешных архивов, минимум два. Архив состоит из `.dump`,
`.counts` и `.sha256`. `pg_export_snapshot()` обеспечивает одну согласованную
версию данных для pg_dump и числа строк во всех таблицах, даже при параллельной
записи в приложение. Неудачная копия не заменяет предыдущие, контейнер становится
unhealthy, пишет ошибку в лог и повторяет попытку через 60 секунд.

Команды на машине деплоя:

```bash
bash scripts/backup.sh
bash scripts/restore-test.sh
bash scripts/rollback.sh
# Либо явно выбрать образ предыдущего коммита:
bash scripts/rollback.sh FULL_PREVIOUS_COMMIT_SHA
```

Проверка восстановления сверяет SHA-256, восстанавливает архив в отдельную
временную БД, сравнивает число строк каждой таблицы с сохранённым snapshot и
проверяет версию Alembic. Затем временная БД удаляется. Рабочая БД не заменяется.
Для локального Compose задайте `COMPOSE_FILE=docker-compose.yml` и
`COMPOSE_PROJECT_NAME` равным имени локального проекта.

Перед последующим production-деплоем автоматически создаётся копия БД. Теги
образов равны полным SHA коммитов; успешные версии записываются в
`.deploy/current` и `.deploy/previous`. Откат меняет образ приложения и worker,
сохраняя БД. Для последующих изменений схемы нужны миграции, совместимые с
предыдущей версией приложения. Здесь первая миграция создаёт исходную схему.
Копии в Docker volume защищают от ошибок приложения, но для защиты от потери
машины следует дополнительно переносить архивы на независимое хранилище.

## Зафиксированные версии и первичные источники

Версии можно обновлять отдельным изменением с повторным сканированием и проверкой:

- [Python 3.12.15 slim-trixie: каталог официальных Docker-образов](https://github.com/docker-library/official-images/blob/master/library/python).
- [PostgreSQL 17.11: каталог официальных Docker-образов](https://github.com/docker-library/official-images/blob/master/library/postgres).
- [uv 0.12.23](https://github.com/astral-sh/uv/releases/tag/0.12.23).
- [Prometheus 3.13.2](https://github.com/prometheus/prometheus/releases/tag/v3.13.2).
- [Grafana 12.4.11](https://github.com/grafana/grafana/releases/tag/v12.4.11).
- [PostgreSQL Exporter 0.19.1](https://github.com/prometheus-community/postgres_exporter/releases/tag/v0.19.1).
- [Compose: ожидание healthy-зависимостей](https://docs.docker.com/compose/how-tos/startup-order/).
- [Jenkins Credentials Binding](https://www.jenkins.io/doc/pipeline/steps/credentials-binding/).
- [PostgreSQL pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html).

Runtime приложения использует Debian Trixie и получает доступные security updates
при сборке; CI запускает `docker build --pull --no-cache`, чтобы слой обновлений
не оставался в кэше. Это устраняет обнаруженные в прежней базе Bookworm CRITICAL-находки
без исключений из Trivy: исправленные версии SQLite и zlib указаны в
[Debian tracker для SQLite](https://security-tracker.debian.org/tracker/CVE-2025-7458)
и [Debian tracker для zlib](https://security-tracker.debian.org/tracker/CVE-2023-45853),
а исправления Perl — в
[Debian tracker для Perl](https://security-tracker.debian.org/tracker/CVE-2026-13221).
Проверка CRITICAL остаётся обязательной для каждого нового образа; наличие
обновлённой базы само по себе не подтверждает результат сканирования.
