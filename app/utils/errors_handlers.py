"""HTTP error translation; domain exceptions have no FastAPI dependencies."""

import re
from collections.abc import Mapping
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

from app.errors import DATABASE_UNAVAILABLE, PROVIDER_UNAVAILABLE, ErrorDefinition, error_definition
from app.exceptions import Conflict, GameNotFound, NotFound, ProviderUnavailable
from app.metrics import DATABASE_READY
from app.schemas.errors import ProblemDetails, ValidationErrorItem, ValidationProblemDetails
from app.utils.error_responses import PROBLEM_MEDIA_TYPE

_SAFE_DETAILS = frozenset(
    {
        "Game not found in local catalog; look up its details first",
        "Watchlist not found",
        "Watchlist item not found",
        "Game is already in this watchlist",
    }
)
_VALIDATION_MESSAGES = {
    "missing": "Field is required",
    "extra_forbidden": "Unexpected field",
    "json_invalid": "Request body must contain valid JSON",
    "greater_than_equal": "Value must meet the minimum allowed value",
    "greater_than": "Value must be above the minimum allowed value",
    "less_than_equal": "Value must meet the maximum allowed value",
    "less_than": "Value must be below the maximum allowed value",
    "string_too_short": "Value is too short",
    "string_too_long": "Value is too long",
    "string_pattern_mismatch": "Value does not match the required format",
    "decimal_max_digits": "Value has too many digits",
    "decimal_max_places": "Value has too many decimal places",
    "decimal_whole_digits": "Value has too many integer digits",
    "int_parsing": "Value must be an integer",
    "int_type": "Value must be an integer",
    "bool_parsing": "Value must be a boolean",
    "bool_type": "Value must be a boolean",
    "decimal_parsing": "Value must be a decimal number",
    "decimal_type": "Value must be a decimal number",
    "finite_number": "Value must be finite",
    "string_type": "Value must be a string",
    "value_error": "Value does not satisfy the request constraints",
}
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def _trace_id(request: Request) -> UUID:
    current = getattr(request.state, "trace_id", None)
    try:
        identifier = UUID(str(current)) if current is not None else uuid4()
    except (ValueError, TypeError, AttributeError):
        identifier = uuid4()
    request.state.trace_id = str(identifier)
    return identifier


def problem_response(
    request: Request,
    status: int,
    *,
    definition: ErrorDefinition | None = None,
    detail: str | None = None,
    headers: Mapping[str, str] | None = None,
    errors: list[ValidationErrorItem] | None = None,
) -> JSONResponse:
    definition = definition or error_definition(status)
    trace_id = _trace_id(request)
    request.state.error_code = definition.code
    data = {
        "type": definition.type,
        "status": status,
        "title": definition.title,
        "detail": detail or definition.detail,
        "instance": f"urn:uuid:{uuid4()}",
        "trace_id": trace_id,
        "code": definition.code,
    }
    if errors is not None:
        problem = ValidationProblemDetails(**data, errors=errors)
    else:
        problem = ProblemDetails(**data)
    response_headers = dict(headers or {})
    response_headers["X-Request-Id"] = str(trace_id)
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(mode="json", by_alias=True),
        headers=response_headers,
        media_type=PROBLEM_MEDIA_TYPE,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    headers = {
        name: value
        for name, value in (exc.headers or {}).items()
        if name.lower() in {"www-authenticate", "retry-after", "allow"}
    }
    return problem_response(request, exc.status_code, headers=headers)


async def not_found_handler(request: Request, exc: NotFound | GameNotFound) -> JSONResponse:
    detail = "Game not found" if isinstance(exc, GameNotFound) else None
    if isinstance(exc, NotFound) and str(exc) in _SAFE_DETAILS:
        detail = str(exc)
    return problem_response(request, 404, detail=detail)


async def conflict_handler(request: Request, exc: Conflict | IntegrityError) -> JSONResponse:
    detail = str(exc) if isinstance(exc, Conflict) and str(exc) in _SAFE_DETAILS else None
    return problem_response(request, 409, detail=detail)


async def provider_unavailable_handler(request: Request, exc: ProviderUnavailable) -> JSONResponse:
    try:
        retry_after = max(1, min(int(exc.retry_after), 86400))
    except (ValueError, TypeError, OverflowError):
        retry_after = 30
    return problem_response(
        request,
        503,
        definition=PROVIDER_UNAVAILABLE,
        headers={"Retry-After": str(retry_after)},
    )


async def database_unavailable_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    DATABASE_READY.set(0)
    return problem_response(request, 503, definition=DATABASE_UNAVAILABLE)


def _validation_field(location: tuple) -> str:
    # A location may contain arbitrary dictionary keys. Only identifier-like field names
    # and array indices are returned; input values and exception context are discarded.
    parts = [
        str(part)
        if isinstance(part, int)
        else part
        if isinstance(part, str) and _IDENTIFIER.fullmatch(part)
        else "field"
        for part in location
    ]
    return ".".join(parts) or "request"


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        error_type = error.get("type", "value_error")
        if not isinstance(error_type, str) or not _IDENTIFIER.fullmatch(error_type):
            error_type = "value_error"
        location = error.get("loc", ())
        # Extra keys are arbitrary user data even when they look like identifiers.
        if error_type == "extra_forbidden" and location:
            location = (*location[:-1], "field")
        errors.append(
            ValidationErrorItem(
                field=_validation_field(location),
                type_=error_type,
                message=_VALIDATION_MESSAGES.get(error_type, "Value is invalid"),
            )
        )
    return problem_response(request, 422, errors=errors)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never serialize/log exc text, repr or traceback: persistence exceptions can include DSNs.
    request.state.error_type = type(exc).__name__
    return problem_response(request, 500)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(NotFound, not_found_handler)
    app.add_exception_handler(GameNotFound, not_found_handler)
    app.add_exception_handler(Conflict, conflict_handler)
    app.add_exception_handler(IntegrityError, conflict_handler)
    app.add_exception_handler(ProviderUnavailable, provider_unavailable_handler)
    app.add_exception_handler(SQLAlchemyError, database_unavailable_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
