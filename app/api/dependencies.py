import secrets
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings
from app.dependencies.dispatcher_register import get_usecase_dispatcher
from app.dispatcher import UseCaseDispatcher

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


def get_dispatcher() -> UseCaseDispatcher:
    return get_usecase_dispatcher()


DispatcherDependency = Annotated[UseCaseDispatcher, Depends(get_dispatcher)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
