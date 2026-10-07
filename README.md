# Game Radar

Backend для отслеживания цен PC-игр: поиск, wishlist с желаемой ценой, фильтр
Steam, собственная история наблюдений, сводка стоимости и журнал срабатывания
порогов.

Стек: Python 3.12, FastAPI, SQLAlchemy (async ORM), Alembic, PostgreSQL,
Docker Compose. Архитектура: тонкий endpoint → frozen UseCase → Dispatcher →
Handler → Repository.

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

Нужны Git и Docker с Compose v2. Все компоненты (API, worker, PostgreSQL)
описаны в `docker-compose.yml`.

```powershell
Copy-Item .env.example .env
# В .env замените POSTGRES_PASSWORD и API_KEY (не короче 16 символов) случайными значениями.
docker compose up -d --build --wait
docker compose ps
```

Миграции Alembic выполняются перед запуском API; worker стартует после готовности API.

- Swagger UI: <http://localhost:8000/docs>. Нажмите **Authorize** и введите `API_KEY` из `.env`.
- OpenAPI: <http://localhost:8000/openapi.json>.
- Health: <http://localhost:8000/health>.

Остановка с сохранением данных: `docker compose down`.

## Секреты

Пароль БД и API-ключ передаются только через переменные окружения. `.env` указан
в `.gitignore`, в репозитории лежит только шаблон `.env.example`.

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
