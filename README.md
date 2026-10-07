# Game Radar

Backend для отслеживания цен PC-игр: поиск, wishlist с желаемой ценой, фильтр
Steam, собственная история наблюдений, сводка стоимости и журнал срабатывания
порогов.

Стек: Python 3.12, FastAPI, SQLAlchemy (async ORM, asyncpg), Alembic, PostgreSQL,
Docker Compose, Jenkins, Prometheus, Grafana. Архитектура: тонкий endpoint →
frozen UseCase → Dispatcher → Handler → Repository.

## Что делает сервис

- Принимает запросы пользователя через REST API, обрабатывает их и возвращает результат.
- Обращается к стороннему API [CheapShark](https://apidocs.cheapshark.com/) за ценами
  и сохраняет каталог игр.
- Хранит wishlist, желаемую цену и предпочтение `steam_only` для каждой игры в PostgreSQL
  и выдаёт их по запросу.
- Фоновый worker периодически обновляет цены, записывает снимки и создаёт запись
  в журнале при достижении желаемой цены; повторная проверка дубликат не создаёт.

Цена возвращается строкой Decimal, например `"3.99"`; валюта — **USD**.
`PRICE_SOURCE=mock` использует вымышленные фиксированные цены без внешних запросов:
LEGO Batman — Steam `3.99`, BioShock — `7.49`, Portal 2 — `4.99`.
`PRICE_SOURCE=cheapshark` берёт реальные предложения.

## Запуск в Docker Compose

Нужны Git и Docker с Compose v2. Все компоненты описаны в `docker-compose.yml`:
`db` (PostgreSQL), `app` (API), `worker`, `prometheus`, `grafana`.

```powershell
Copy-Item .env.example .env
# В .env замените POSTGRES_PASSWORD, API_KEY и GRAFANA_PASSWORD случайными значениями.
docker compose up -d --build --wait
docker compose ps
```

Миграции Alembic выполняются перед запуском API. У всех контейнеров есть
`healthcheck`, порядок запуска задан через `depends_on: condition: service_healthy`.

| Что | Адрес |
| --- | --- |
| Swagger UI (кнопка **Authorize**, ключ `API_KEY` из `.env`) | <http://localhost:8000/docs> |
| OpenAPI | <http://localhost:8000/openapi.json> |
| Health | <http://localhost:8000/health> |
| Метрики Prometheus | <http://localhost:8000/metrics> |
| Prometheus | <http://localhost:9090> |
| Grafana (логин `admin`, пароль `GRAFANA_PASSWORD`) | <http://localhost:3000> |

Остановка с сохранением данных: `docker compose down`.

## Настройки и секреты

Все настройки приложения и их значения по умолчанию собраны в `game_radar/config.py`.
Пароли и ключи передаются только через переменные окружения: `.env` указан
в `.gitignore`, в репозитории лежит только шаблон `.env.example`.

## CI/CD (Jenkins)

Пайплайн описан в `Jenkinsfile` и работает на двух машинах:

- **машина 1 — Jenkins**: проверка кода и сборка Docker-образа;
- **машина 2 — `DEPLOY_HOST`**: запуск всех контейнеров через `docker compose`.

| Стадия | Что делает |
| --- | --- |
| Lint & tests | `ruff check`, `ruff format --check`, `pytest`; ошибка останавливает пайплайн |
| Build | `docker build` образа `game-radar` на машине 1 |
| Deploy | по SSH копирует `docker-compose.yml` и `monitoring/`, пишет `.env` из Jenkins Credentials, переносит образ (`docker save` → `docker load`) и выполняет `docker compose up -d --wait` |
| Smoke | `GET http://DEPLOY_HOST:8000/health`, ожидается `"status":"ok"` |

Настройка Jenkins:

1. Создайте Pipeline-job из этого GitHub-репозитория (Pipeline script from SCM, `Jenkinsfile`).
2. Добавьте Jenkins Credentials:

   | ID | Тип | Назначение |
   | --- | --- | --- |
   | `deploy-ssh` | SSH Username with private key | доступ к машине деплоя |
   | `postgres-password` | Secret text | пароль PostgreSQL |
   | `api-key` | Secret text | ключ `X-API-Key` |
   | `grafana-password` | Secret text | пароль администратора Grafana |

3. В параметрах сборки укажите `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH` и `PRICE_SOURCE`.

На машине Jenkins нужны `python3`, `docker` и `curl`; на машине деплоя — Docker
с Compose v2 и SSH-доступ пользователя `DEPLOY_USER` к Docker.

## Мониторинг

API отдаёт метрики на `/metrics` (`prometheus-fastapi-instrumentator`), Prometheus
собирает их (`monitoring/prometheus.yml`), Grafana получает источник данных и дашборд
**Game Radar — FastAPI** автоматически (`monitoring/grafana/`): доступность, запросы
в секунду, доля ошибок 5xx, задержка p50/p95/p99, CPU и память процесса.

## Проверка кода

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\ruff check .
.venv\Scripts\python -m pytest
```

Тесты не требуют БД и сети: репозитории и диспетчер подменяются.

## Основные endpoints

Все операции `/games` и `/watchlists` требуют заголовок `X-API-Key`.

| Операция | Endpoint |
| --- | --- |
| Поиск | `GET /games/search?query=lego` |
| Текущие предложения | `GET /games/{game_id}` |
| История наблюдавшихся цен | `GET /games/{game_id}/history?limit=100&offset=0` |
| Создать / получить все wishlist | `POST /watchlists`, `GET /watchlists` |
| Получить / удалить wishlist | `GET /watchlists/{id}`, `DELETE /watchlists/{id}` |
| Добавить игру | `POST /watchlists/{id}/items` |
| Изменить порог/Steam-фильтр | `PATCH /watchlists/{id}/items/{item_id}` |
| Удалить игру из списка | `DELETE /watchlists/{id}/items/{item_id}` |
| Сводка | `GET /watchlists/{id}/summary` |
| Журнал срабатываний | `GET /watchlists/{id}/notifications` |
| Обновить предложения | `POST /watchlists/{id}/refresh` |

Пример тела создания wishlist: `{"name":"Хочу купить"}`. Пример добавления игры:

```json
{"gameId":"612","targetPrice":"4.00","steamOnly":true}
```

Сценарий для демонстрации в Swagger: поиск → wishlist → игра → summary →
notifications → history. В mock ожидается Steam `3.99`, достигнутый порог `4.00`
и одна запись журнала.

Ошибки возвращаются в формате Problem Details (RFC 9457).
