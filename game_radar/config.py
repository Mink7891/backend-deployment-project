import os
import tempfile
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

        # Те же переменные читает контейнер PostgreSQL в docker-compose.yml.
        self.POSTGRES_USER = os.environ.get("POSTGRES_USER", "game_radar")
        self.POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
        self.POSTGRES_DB = os.environ.get("POSTGRES_DB", "game_radar")
        self.POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "db")
        self.POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
        # Драйвер asyncpg; если DATABASE_URL не задан, адрес собирается из POSTGRES_*.
        self.DATABASE_URL = os.environ.get("DATABASE_URL") or (
            f"postgresql+asyncpg://{quote(self.POSTGRES_USER)}:{quote(self.POSTGRES_PASSWORD)}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

        # Общий ключ доступа к операциям /games и /watchlists (заголовок X-API-Key).
        self.API_KEY = os.environ.get("API_KEY", "")

        # mock — вымышленные фиксированные цены без внешних запросов;
        # cheapshark — реальные предложения CheapShark в USD.
        self.PRICE_SOURCE = os.environ.get("PRICE_SOURCE", "mock")
        self.CHEAPSHARK_BASE_URL = os.environ.get(
            "CHEAPSHARK_BASE_URL", "https://www.cheapshark.com/api/1.0"
        )
        self.CHEAPSHARK_USER_AGENT = os.environ.get(
            "CHEAPSHARK_USER_AGENT", "GameRadar-Educational/0.1"
        )
        self.CHEAPSHARK_TIMEOUT = float(os.environ.get("CHEAPSHARK_TIMEOUT", "10"))

        # Период фонового обновления цен worker'ом.
        self.REFRESH_INTERVAL_SECONDS = int(os.environ.get("REFRESH_INTERVAL_SECONDS", "3600"))
        # Сколько секунд сохранённые цены считаются свежими и не запрашиваются повторно.
        self.REFRESH_MIN_INTERVAL_SECONDS = int(
            os.environ.get("REFRESH_MIN_INTERVAL_SECONDS", "300")
        )

        # Идентификатор магазина Steam в CheapShark и валюта цен CheapShark.
        self.STEAM_STORE_ID = os.environ.get("STEAM_STORE_ID", "1")
        self.CURRENCY = os.environ.get("CURRENCY", "USD")

        # Файл-пульс worker'а для healthcheck контейнера и период его обновления.
        self.WORKER_HEARTBEAT_PATH = os.environ.get(
            "WORKER_HEARTBEAT_PATH", os.path.join(tempfile.gettempdir(), "worker-heartbeat")
        )
        self.WORKER_HEARTBEAT_INTERVAL_SECONDS = int(
            os.environ.get("WORKER_HEARTBEAT_INTERVAL_SECONDS", "30")
        )


settings = Settings()
