"""Pydantic-схемы ошибок согласно RFC 9457 Problem Details."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProblemDetails(BaseModel):
    """Единый формат ошибок согласно RFC 9457 (базовый)."""

    model_config = ConfigDict(populate_by_name=True)

    type_: str = Field(
        default="",
        alias="type",
        description="Стабильный URI на документацию ошибки.",
    )
    status: int = Field(..., description="HTTP статус код")
    title: str = Field(..., description="Краткое описание ошибки")
    detail: str = Field(..., description="Подробное описание ошибки")
    instance: UUID | None = Field(
        default=None,
        description="URI, идентифицирующий конкретный экземпляр проблемы.",
    )
    trace_id: UUID | None = Field(
        default=None,
        description="ID трассировки",
        alias="traceId",
    )
    code: str = Field(..., description="Внутренний код ошибки")
