"""OpenAPI response descriptions generated from the public error catalog."""

from typing import Any
from uuid import UUID

from app.errors import error_definition
from app.schemas.errors import ProblemDetails, ValidationErrorItem, ValidationProblemDetails

PROBLEM_MEDIA_TYPE = "application/problem+json"
_EXAMPLE_TRACE = UUID("00000000-0000-4000-8000-000000000001")
_EXAMPLE_INSTANCE = "urn:uuid:00000000-0000-4000-8000-000000000002"


def _inline_schema(model: type[ProblemDetails]) -> dict[str, Any]:
    """Inline local Pydantic definitions so refs remain valid in OpenAPI content."""
    schema = model.model_json_schema(by_alias=True)
    definitions = schema.pop("$defs", {})

    def resolve(value: Any) -> Any:
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, dict):
            reference = value.get("$ref", "")
            if reference.startswith("#/$defs/"):
                return resolve(definitions[reference.removeprefix("#/$defs/")])
            return {key: resolve(item) for key, item in value.items()}
        return value

    return resolve(schema)


def get_error_responses(*status_codes: int) -> dict[int, dict[str, Any]]:
    responses = {}
    for status in status_codes:
        definition = error_definition(status)
        data = {
            "type": definition.type,
            "status": status,
            "title": definition.title,
            "detail": definition.detail,
            "instance": _EXAMPLE_INSTANCE,
            "trace_id": _EXAMPLE_TRACE,
            "code": definition.code,
        }
        model: type[ProblemDetails] = ProblemDetails
        if status == 422:
            model = ValidationProblemDetails
            data["errors"] = [
                ValidationErrorItem(
                    field="body.target_price",
                    type_="greater_than_equal",
                    message="Value must meet the minimum allowed value",
                )
            ]
        example = model(**data).model_dump(mode="json", by_alias=True)
        responses[status] = {
            "description": definition.title,
            "content": {PROBLEM_MEDIA_TYPE: {"schema": _inline_schema(model), "example": example}},
            "headers": {
                "X-Request-Id": {
                    "description": "Server-generated correlation UUID, matching traceId",
                    "schema": {"type": "string", "format": "uuid"},
                }
            },
        }
        if status == 401:
            responses[status]["headers"]["WWW-Authenticate"] = {
                "schema": {"type": "string"},
                "example": "APIKey",
            }
        if status == 503:
            responses[status]["headers"]["Retry-After"] = {
                "description": "Delay in seconds when the price provider is unavailable",
                "schema": {"type": "string"},
            }
    return responses
