# Game Radar

Backend для отслеживания цен PC-игр: поиск, wishlist с желаемой ценой, фильтр
Steam, собственная история наблюдений, сводка стоимости и журнал срабатывания
порогов. Проект рассчитан на учебное развёртывание через Jenkins на двух машинах.

Стек: Python 3.12, FastAPI, SQLAlchemy Core, Alembic, PostgreSQL, Docker Compose,
Prometheus/Grafana, JMeter. **Use Case pattern** разделяет данные операции
и её выполнение: frozen Command/Query → Dispatcher → Handler. Handler содержит
бизнес-правила и управляет `Connection.begin()`; Repository выполняет Core SQL
без commit/rollback. Pydantic DTO и dataclass Views отделены от таблиц.

## Что делает сервис

- Ищет игры через [CheapShark](https://apidocs.cheapshark.com/) и сохраняет каталог.
- Хранит несколько wishlist, желаемую цену и предпочтение `steam_only` для каждой игры.
- Периодически обновляет предложения, записывает снимки цен и проверяет пороги.
- Создаёт запись журнала при переходе в состояние «желаемая цена достигнута»;
  повторная проверка того же состояния не создаёт дубликат.
- Показывает историю наблюдений и общую стоимость выбранного wishlist.

Цена возвращается строкой Decimal, например `"3.99"`; валюта — **USD**. CheapShark
включает Steam, однако это не региональные рублёвые цены Steam. История начинается
с наблюдений нашего сервиса. Ответы содержат источник `cheapshark` или `mock`.
Сводка может вернуть `mixed`, если список содержит наблюдения разных источников
после смены режима; источник конкретной игры и снимка сохраняется отдельно.

`PRICE_SOURCE=mock` использует вымышленные фиксированные цены без внешних запросов:
LEGO Batman — Steam `3.99`, BioShock — `7.49`, Portal 2 — `4.99`. Другие магазины
в mock имеют отдельные цены. Доставка событий в Telegram отложена; сейчас
реализован журнал в БД/API. Отдельные пользователи и личная авторизация пока
не предусмотрены: один общий `X-API-Key` защищает все операции с играми и wishlist.

## Быстрый запуск Docker Compose

Нужны Git и Docker с Compose v2 и Linux-контейнерами. На Windows команды ниже
выполняются из PowerShell в корне репозитория.

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
```

Перед первым запуском в `.env` замените `POSTGRES_PASSWORD`, `API_KEY` и `GRAFANA_PASSWORD` случайными
значениями. `API_KEY` должен содержать хотя бы 16 символов, рекомендуется 32 и
больше. Если пароль БД содержит специальные символы, правильно закодируйте его
в `DATABASE_URL`; случайный hex-пароль упрощает настройку. `.env` остаётся локальным.
По умолчанию пример запускается в автономном режиме `PRICE_SOURCE=mock`.

```powershell
$env:IMAGE_REPOSITORY = 'game-radar'
$env:IMAGE_TAG = 'dev'
docker compose -p game-radar --profile monitoring --profile operations up -d --build --wait
docker compose -p game-radar ps
```

Миграции выполняются перед запуском API; worker ждёт готовности приложения.
Откройте:

- Swagger: <http://localhost:8000/docs> — кнопка **Authorize**, ключ из `.env`.
- Health: <http://localhost:8000/health>.
- Prometheus: <http://localhost:9090>.
- Grafana: <http://localhost:3000> — логин/пароль из `.env`, dashboard **Game Radar — API and PostgreSQL**.

Чтобы брать реальные предложения, установите `PRICE_SOURCE=cheapshark` и снова
выполните `docker compose -p game-radar up -d`. Для корректного обновления worker
и API используются одинаковые env-параметры. Ошибки внешнего провайдера возвращают
503 с `Retry-After`; автономный mock даёт воспроизводимую демонстрацию.

Обычная остановка сохраняет данные:

```powershell
docker compose -p game-radar --profile monitoring --profile operations down
```

## Разработка и проверки

Нужен [uv](https://docs.astral.sh/uv/). Lock-файл фиксирует зависимости:

```powershell
uv sync --locked --group dev --python 3.12
uv run --no-sync python scripts/generate_schemas.py --check
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q
```

Тесты создают отдельную SQLite в памяти и запрещают исходящие HTTP-запросы.
Проверяются API/валидация/ключ, команды и обработчики Use Case, Steam-фильтр и суммы,
кэш и история, переходы порога и дедупликация, отказ провайдера, его HTTP-адаптер
через MockTransport, метрики и JTL gate. Тесты не обращаются к рабочей БД.

Для быстрого запуска API без Docker используйте отдельную SQLite для разработки;
production Compose работает с PostgreSQL:

```powershell
$env:DATABASE_URL = 'sqlite+pysqlite:///./game-radar-dev.db'
$env:API_KEY = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
$env:PRICE_SOURCE = 'mock'
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --no-access-log
```

Для фонового обновления запустите `uv run python -m app.worker` в другом терминале
с теми же переменными. SQLite предназначена для локальной разработки; проверка
миграций, транзакций и эксплуатации на PostgreSQL выполняется через Compose.
Перед возвратом к Compose уберите PowerShell-переопределения `DATABASE_URL`,
`API_KEY` и `PRICE_SOURCE`, чтобы Compose использовал `.env`.

## Основные endpoints

Все операции `/games` и `/watchlists` требуют заголовок `X-API-Key`.
`/health`, `/metrics`, Swagger и OpenAPI доступны без ключа.

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
{"game_id":"612","target_price":"4.00","steam_only":true}
```

Канонический JSON согласованного API-контракта использует camelCase:
`{"gameId":"612","targetPrice":"4.00","steamOnly":true}`. Прежние snake_case
имена принимаются на входе; ответы используют camelCase. Схемы генерируются
из [OpenAPI 3.1.0 контракта](doc/game-radar-api.yaml) через
`scripts/generate_schemas.py`. Ошибки представлены как Problem Details.

Таблицы `app/models/tables.py` генерируются sqlacodegen; инструкция и границы
слоёв описаны в [архитектуре](docs/architecture.md). Генерация по миграции
не заменяет проверку схемы на PostgreSQL.

Swagger показывает схемы и позволяет пройти сценарий: поиск → wishlist → игра
→ summary → notifications → history. В mock ожидается Steam `3.99`, достигнутый
порог `4.00` и одна запись журнала. Refresh уважает минимальный интервал кэша:
многократные нажатия не вызывают лишние запросы провайдеру и не создают дубликаты.

## Jenkins: две машины, реестр и нагрузка

Первая Linux-машина — Jenkins agent с label `linux-ci`, Docker, uv/Python 3.12,
Trivy, JMeter 5.6.3 и Java. Вторая — Linux с Docker/Compose, SSH и доступом к
реестру. Jenkins job читает этот GitHub-репозиторий и `Jenkinsfile`.
Нужен Jenkins Credentials Binding; публикация тестов использует JUnit plugin.

Настройте следующие Jenkins Credentials:

| ID | Тип / назначение |
| --- | --- |
| `registry-auth` | Username/password, публикация и pull образа |
| `deploy-ssh` | SSH private key, доступ на машину деплоя |
| `deploy-known-hosts` | Secret file с проверенным SSH host key второй машины |
| `radar-api-key` | Secret text, общий API-ключ |
| `postgres-password` | Secret text, пароль БД |
| `grafana-password` | Secret text, пароль Grafana |

В параметрах job задайте реальный `IMAGE_REPOSITORY`, `DEPLOY_HOST`, `DEPLOY_USER`
и `DEPLOY_PATH`. Пользователь деплоя должен иметь доступ к Docker и своему
каталогу. Закрепите SSH host key; Jenkins не отключает его проверку. Сервис
должен быть доступен первой машине по портам `PROD_PORT`/`LOAD_PORT` в учебной сети.

Pipeline: проверка параметров → линтер/тесты → multi-stage сборка → Trivy
CRITICAL gate → push образа с полным commit SHA → pull и deploy на второй
машине → smoke → отдельный mock-стек → JMeter non-GUI → gate ошибок/p95.
После сбоя стадия не продолжается; результаты тестов, Trivy и нагрузки
архивируются. Deployment использует готовый образ без сборки на второй машине.

Нагрузочная среда имеет отдельные `.env.load`, project `game-radar-load`, API на
порту 8001 и БД `radar_load`; API и worker принудительно используют mock. Её
Prometheus/Grafana работают на 9091/3001 и собирают метрики именно тестового стека.
Перед прогоном и после него очищаются только её временные тома. Рабочий проект
`game-radar` использует отдельные тома. Генератор находится на первой машине.
Перед очисткой Jenkins сохраняет временные ряды в `reports/load-monitoring.json`.
Для живого просмотра тестовой Grafana используйте SSH-туннель к порту 3001.
[Подготовка хостов, детали инфраструктуры и доступ к графикам](infrastructure/README.md).

В Jenkins по умолчанию три ступени по 5 пользователей, интервал 40 секунд,
ramp 10 секунд: 5 → 10 → 15 пользователей. План включает четыре операции,
две записи в БД, JSON assertions и параметры адреса. Gate останавливает CI
при ошибках **выше 1%** или p95 **выше 1000 мс**. Порог — начальный бюджет
ответа до секунды, который нужно подтвердить/обосновать на выбранных VM.
[Команды, методика и формат результатов](load-tests/README.md).

## Backup и rollback

Профиль `operations` запускает backup-сервис: дамп PostgreSQL по расписанию,
по умолчанию раз в сутки, хранение семи архивов. Архивы лежат в отдельном томе
`postgres_backups`. На Linux-хосте production ручная проверка:

```bash
bash scripts/backup.sh
bash scripts/restore-test.sh
```

Restore создаёт отдельную тестовую БД, восстанавливает последний архив и
проверяет данные; рабочую БД не заменяет. Для локального Compose укажите
`COMPOSE_FILE=docker-compose.yml`, `COMPOSE_PROJECT_NAME=game-radar` и вызывайте
те же Bash-скрипты. Для Windows подойдёт Bash-среда с доступом к Docker.

На второй машине повторный deploy фиксирует текущий и предыдущий commit:

```bash
bash scripts/deploy.sh FULL_COMMIT_SHA production
bash scripts/rollback.sh
```

Вместо `FULL_COMMIT_SHA` нужен полный реальный SHA опубликованного образа.
Rollback возвращает предыдущий образ; база не откатывается автоматически.
Изменения схемы должны оставаться совместимыми с предыдущей версией приложения.
Перед обновлением уже развёрнутого production-стека deploy делает резервную
копию текущей БД; при первой установке backup-сервис начинает после готовности схемы.

## Подготовка к сдаче

[Архитектура](docs/architecture.md), [чек-лист задания](docs/requirements-checklist.md),
[работа двух участников](docs/team-plan.md), [Word-отчёт](docs/GameRadar-report.docx).

[Результаты локальных проверок 6 и 7 октября](docs/local-verification.md): Compose,
PostgreSQL, backup/restore, Trivy и короткий smoke-прогон JMeter **до рефакторинга
7 октября на Core/Dispatcher/Handler**. Эти измерения не подтверждают новую
сборку автоматически. 7 октября новая версия прошла 134 теста, Ruff,
воспроизводимость кодогенерации, HTTP smoke, конкурентные проверки и Alembic
check на PostgreSQL. Повторный Trivy: 0 CRITICAL; короткий JMeter: 338 запросов,
0 ошибок, p95 26 мс, p99 2602 мс. Рабочие и нагрузочные сервисы после проверки
остановлены; постоянные тома сохранены, временные тома нагрузки удалены.
Двухмашинный CI и полная нагрузка остаются отдельными проверками.

Код и конфигурации подготовлены. Для подтверждения уровня «отлично» требуется
реальный успешный pipeline на двух разных машинах, JTL/HTML и графики нагрузки,
демонстрация Trivy, backup/restore, rollback и изменения кода через CI/CD.
Локальная проверка на одном компьютере не заменяет эти доказательства.
Word-отчёт обновлён 7 октября: 31 страница со схемами новой архитектуры,
листингами конфигураций и фактическими локальными результатами. Все страницы
отрендерены и проверены, номера оглавления сверены с PDF. Измерения и снимки
Swagger/Grafana 6 октября явно отделены от проверок новой Core-версии 7 октября.
Перед сдачей заполните поле преподавателя и реальный вклад участников, добавьте
указанные доказательства с commit SHA и параметрами обеих машин (CPU/RAM, ОС, сеть).
В нагрузочном отчёте обоснуйте p95 и определите точку насыщения.
Затем загрузите `.docx` в СДО.
