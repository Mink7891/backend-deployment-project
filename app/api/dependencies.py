import secrets
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.application.ports import PriceProvider, UnitOfWork
from app.config import Settings, get_settings
from app.db import get_session
from app.infrastructure.repositories import SqlAlchemyUnitOfWork
from app.providers import get_provider

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    key: Annotated[str | None, Depends(api_key_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    expected = settings.api_key.get_secret_value()
    if key is None or not secrets.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "APIKey"},
        )


def get_uow(session: Annotated[Session, Depends(get_session)]) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session)


UowDependency = Annotated[UnitOfWork, Depends(get_uow)]
ProviderDependency = Annotated[PriceProvider, Depends(get_provider)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
