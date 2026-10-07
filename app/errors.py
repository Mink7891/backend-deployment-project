"""Public error definitions; request identifiers are created at response time."""

from dataclasses import dataclass
from http import HTTPStatus
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ErrorDefinition:
    status: int
    title: str
    detail: str
    code: str
    type: str


def _error(status: int, code: str, detail: str) -> ErrorDefinition:
    return ErrorDefinition(
        status=status,
        title=HTTPStatus(status).phrase,
        detail=detail,
        code=code,
        type=f"urn:gameradar:error:{code.lower().replace('_', '-')}",
    )


DEFAULT_ERRORS = MappingProxyType(
    {
        401: _error(401, "UNAUTHORIZED", "Invalid or missing API key"),
        403: _error(403, "FORBIDDEN", "Access to this resource is forbidden"),
        404: _error(404, "NOT_FOUND", "The requested resource was not found"),
        405: _error(405, "METHOD_NOT_ALLOWED", "This HTTP method is not allowed"),
        409: _error(409, "CONFLICT", "Resource already exists or was removed"),
        422: _error(422, "VALIDATION_ERROR", "Request validation failed"),
        500: _error(500, "INTERNAL_SERVER_ERROR", "An unexpected server error occurred"),
        503: _error(503, "SERVICE_UNAVAILABLE", "Service is temporarily unavailable"),
    }
)

PROVIDER_UNAVAILABLE = _error(
    503, "PROVIDER_UNAVAILABLE", "Price provider is temporarily unavailable"
)
DATABASE_UNAVAILABLE = _error(503, "DATABASE_UNAVAILABLE", "Database is temporarily unavailable")


def error_definition(status: int) -> ErrorDefinition:
    if status in DEFAULT_ERRORS:
        return DEFAULT_ERRORS[status]
    try:
        title = HTTPStatus(status).phrase
    except ValueError:
        title = "HTTP Error"
    return ErrorDefinition(
        status=status,
        title=title,
        detail="The request could not be completed",
        code="HTTP_ERROR",
        type="about:blank",
    )
