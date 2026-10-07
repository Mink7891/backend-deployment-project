from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: str
    api_key: SecretStr = Field(min_length=16)
    price_source: Literal["mock", "cheapshark"] = "mock"
    cheapshark_base_url: str = "https://www.cheapshark.com/api/1.0"
    cheapshark_user_agent: str = Field(default="GameRadar/0.1 (student project)", min_length=3)
    refresh_interval_seconds: int = Field(default=3600, ge=1, le=86400)
    refresh_min_interval_seconds: int = Field(default=300, ge=0, le=86400)

    @field_validator("cheapshark_base_url")
    @classmethod
    def validate_provider_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("CHEAPSHARK_BASE_URL must be an HTTP(S) base URL without credentials")
        return value.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def normalize_postgres_url(cls, value: str) -> str:
        # Hosted services commonly provide these aliases; always use psycopg 3.
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
