# Архитектура

Архитектура UseCase / Dispatcher: эндпоинт формирует UseCase и передаёт его
диспетчеру вместе с `AsyncSession`, Handler выполняет бизнес-логику и управляет
транзакцией, Repository обращается к PostgreSQL через SQLAlchemy (async ORM).

```
Клиент → endpoint → UseCase → UseCaseDispatcher → Handler → Service / Repository → PostgreSQL
                                                          └→ Adapter → CheapShark API
```

## Слои

- `main.py` — FastAPI-приложение: lifespan, middleware, обработчики ошибок, роутер.
- `game_radar/api/v1/endpoints/` — тонкие эндпоинты: формируют UseCase и вызывают
  `dispatcher.dispatch(usecase, session)`.
- `game_radar/usecases/` — frozen dataclass'ы, описывают намерение (команды и запросы).
- `game_radar/usecase_handlers/` — по одному `<action>_handler.py` на UseCase,
  бизнес-логика и `async with session.begin()`.
- `game_radar/dependencies/dispatcher_register.py` — DI: создаёт репозитории,
  адаптер и сервисы один раз и регистрирует `Handler(...).handle` для каждого UseCase.
- `game_radar/services/` — логика, общая для нескольких хендлеров: обновление цен
  с кешем (`GameRefreshService`), журнал порогов (`PriceAlertService`), расчёты цены
  (`PricingActions`).
- `game_radar/repositories/database/` — асинхронные репозитории, по одному на таблицу;
  commit/rollback не вызывают.
- `game_radar/database/` — ORM-модели, engine, сессия.
- `game_radar/adapters/` — HTTP-клиент CheapShark API и офлайн-mock с тем же интерфейсом.
- `game_radar/mapping/` — преобразование JSON CheapShark и ORM-моделей в Pydantic-схемы.
- `game_radar/schemas/` — Pydantic-схемы; ответы API генерируются из
  [OpenAPI-контракта](../doc/game-radar-api.yaml) скриптом `scripts/generate_schemas.py`.
- `game_radar/errors.py` — `ServiceError` и фабрики ошибок; `utils/` превращает их
  в ответы RFC 9457 и документирует в Swagger.
- `game_radar/worker.py` — фоновый процесс, периодически вызывающий
  `RefreshAllWatchedGamesUseCase` через тот же диспетчер.
- `migrations/` — схема БД (Alembic), применяется до запуска API.

## Пример: добавление игры в список

1. `POST /watchlists/{id}/items` → `AddWatchlistItemUseCase`.
2. `AddWatchlistItemHandler` открывает транзакцию, проверяет список и отсутствие дубликата.
3. `GameRefreshService` берёт цены из кеша или запрашивает их у CheapShark,
   сохраняет предложения и снимок истории.
4. Позиция сохраняется, `PriceAlertService` записывает событие в журнал,
   если цена уже не выше желаемой.
5. Маппер возвращает `ItemResponse`; при ошибке транзакция откатывается целиком.

Блокировки PostgreSQL берутся в порядке: игра → родительский список → позиции,
чтобы обновление цен и удаление списка не блокировали друг друга взаимно.
