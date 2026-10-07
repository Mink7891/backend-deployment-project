"""Manually maintained RFC 9457 error schemas, separate from business DTOs."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ValidationErrorItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid", frozen=True)

    field: str
    type_: str = Field(alias="type")
    message: str


class ProblemDetails(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid", frozen=True)

    type: str
    status: int = Field(ge=400, le=599)
    title: str
    detail: str
    instance: str = Field(pattern=r"^urn:uuid:[0-9a-fA-F-]{36}$")
    trace_id: UUID = Field(alias="traceId")
    code: str


class ValidationProblemDetails(ProblemDetails):
    errors: list[ValidationErrorItem]
