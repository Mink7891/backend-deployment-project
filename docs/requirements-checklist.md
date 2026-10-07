# Чек-лист соответствия заданию (блок А)

| Требование | Где выполнено | Что показать на защите |
| --- | --- | --- |
| Полезный backend | Приём данных через API, обработка (пороги, сводка), CheapShark API, хранение wishlist/истории/журнала в БД | Сценарий в Swagger: поиск → wishlist → игра → summary → notifications |
| А1. Git-репозиторий | Этот репозиторий на GitHub | Ссылка на удалённый репозиторий |
| А2. База данных | PostgreSQL, миграции Alembic (`migrations/`) | Данные сохраняются после перезапуска контейнеров |
| А3. Docker и `docker-compose.yml` | `Dockerfile`, `docker-compose.yml`: `db`, `app`, `worker` | `docker compose up -d --build --wait`, `docker compose ps` |
| А4. OpenAPI и Swagger UI | `/docs`, `/openapi.json`, контракт `doc/game-radar-api.yaml` | Swagger UI с авторизацией по `X-API-Key` |
| А5. Секреты вне репозитория | Переменные окружения, `.env` в `.gitignore`, в репозитории только `.env.example` | `git ls-files` без `.env`; содержимое `.env.example` |

На защите нужно явно разделить, что взято из шаблонов, а что сделано
самостоятельно. Если готовый шаблон (например, full-stack-fastapi-template)
не использовался, так и укажите.
