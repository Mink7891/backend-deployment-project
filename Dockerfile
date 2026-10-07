FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Системный пользователь для запуска сервиса
RUN addgroup --system app && adduser --system --ingroup app app

# Сначала только зависимости — слой кешируется, пока requirements.txt не меняется
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app main.py alembic.ini ./
COPY --chown=app:app game_radar ./game_radar
COPY --chown=app:app migrations ./migrations

USER app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
