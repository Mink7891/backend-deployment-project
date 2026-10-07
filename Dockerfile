# Этап 1: установка зависимостей в отдельное виртуальное окружение.
FROM python:3.12-slim AS builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Этап 2: итоговый образ — только окружение и код, без pip-кеша и файлов сборки.
FROM python:3.12-slim AS runtime

# Обновления безопасности ОС, чтобы Trivy не находил исправленные уязвимости базы.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Непривилегированный пользователь для запуска сервиса
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app main.py alembic.ini ./
COPY --chown=app:app game_radar ./game_radar
COPY --chown=app:app migrations ./migrations

USER app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
