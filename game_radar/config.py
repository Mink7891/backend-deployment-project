import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

        # Драйвер asyncpg: postgresql+asyncpg://user:password@host:5432/db
        self.DATABASE_URL = os.environ.get("DATABASE_URL", "")

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


settings = Settings()
