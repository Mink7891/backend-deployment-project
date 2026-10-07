"""Problem Details and structured logs never expose request or exception secrets."""

import io
import json
import logging
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.exceptions import Conflict, NotFound, ProviderUnavailable
from app.log_config import JsonFormatter
from app.log_config import logger as application_logger
from app.middleware.log_middleware import RequestLoggingMiddleware
from app.utils.errors_handlers import register_exception_handlers

SECRET = "private-test-password-that-must-not-appear"


class ValidationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int


@pytest.fixture
def error_application():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter("test-error-service"))
    logger = logging.Logger("test-error-service", level=logging.INFO)
    logger.addHandler(handler)
    application = FastAPI()
    register_exception_handlers(application)
    application.add_middleware(RequestLoggingMiddleware, logger=logger)

    @application.post("/probe/{resource_id}")
    def probe(resource_id: int):
        return {"ok": resource_id > 0}

    @application.post("/validate")
    def validate(body: ValidationPayload):
        return {"quantity": body.quantity}

    @application.get("/failure/{kind}")
    def failure(kind: str):
        if kind == "unauthorized":
            raise HTTPException(
                401,
                detail={"password": SECRET},
                headers={"WWW-Authenticate": "APIKey", "X-Private-Detail": SECRET},
            )
        if kind == "missing":
            raise NotFound(SECRET)
        if kind == "conflict":
            raise Conflict(SECRET)
        if kind == "provider":
            raise ProviderUnavailable(SECRET, retry_after=37)
        if kind == "database":
            raise SQLAlchemyError(f"postgresql://user:{SECRET}@private-db/service")
        raise RuntimeError(f"Unexpected database password={SECRET}")

    with TestClient(application, raise_server_exceptions=False) as client:
        yield client, stream
    handler.close()


def assert_problem(response, status, code):
    assert response.status_code == status
    assert response.headers["content-type"].split(";")[0] == "application/problem+json"
    data = response.json()
    assert {"type", "status", "title", "detail", "instance", "traceId", "code"} <= data.keys()
    assert data["status"] == status and data["code"] == code
    assert isinstance(data["title"], str) and data["title"]
    assert isinstance(data["detail"], str) and data["detail"]
    assert data["type"].startswith("urn:gameradar:error:")
    assert str(UUID(data["traceId"])) == response.headers["X-Request-Id"]
    assert data["instance"].startswith("urn:uuid:")
    UUID(data["instance"].removeprefix("urn:uuid:"))
    assert SECRET not in response.text
    assert "trace_id" not in data
    return data


@pytest.mark.parametrize(
    "kind,status,code",
    [
        ("unauthorized", 401, "UNAUTHORIZED"),
        ("missing", 404, "NOT_FOUND"),
        ("conflict", 409, "CONFLICT"),
        ("provider", 503, "PROVIDER_UNAVAILABLE"),
        ("database", 503, "DATABASE_UNAVAILABLE"),
        ("unexpected", 500, "INTERNAL_SERVER_ERROR"),
    ],
)
def test_errors_preserve_problem_protocol_and_hide_private_exception_details(
    error_application, kind, status, code
):
    client, stream = error_application
    problem = assert_problem(client.get(f"/failure/{kind}"), status, code)
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert len(records) == 1
    record = records[0]
    assert record["trace.id"] == problem["traceId"]
    assert record["error.code"] == code
    assert record["http.response.status_code"] == status
    assert record["log.level"] == ("ERROR" if status >= 500 else "WARNING")
    assert SECRET not in stream.getvalue()


def test_authentication_and_provider_retry_headers_are_preserved(error_application):
    client, _ = error_application
    authentication = client.get("/failure/unauthorized")
    assert authentication.headers["WWW-Authenticate"] == "APIKey"
    assert "X-Private-Detail" not in authentication.headers
    provider = client.get("/failure/provider")
    assert provider.headers["Retry-After"] == "37"


@pytest.mark.parametrize(
    "extra_key", [f"unexpected-{SECRET}", "private_test_password_value_abcdef"]
)
def test_validation_problems_omit_values_context_and_arbitrary_field_names(
    error_application, extra_key
):
    client, stream = error_application
    response = client.post(
        "/validate",
        json={"quantity": SECRET, extra_key: SECRET},
    )
    problem = assert_problem(response, 422, "VALIDATION_ERROR")
    assert len(problem["errors"]) == 2
    assert any(error["field"] == "body.quantity" for error in problem["errors"])
    assert extra_key not in response.text
    for error in problem["errors"]:
        assert set(error) == {"field", "message", "type"}
        assert error["message"]
    assert SECRET not in stream.getvalue()
    assert extra_key not in stream.getvalue()


def test_request_logs_use_route_templates_and_exclude_headers_query_and_bodies(error_application):
    client, stream = error_application
    supplied_request_id = str(uuid4())
    response = client.post(
        "/probe/912345",
        params={"token": SECRET},
        json={"password": SECRET},
        headers={
            "Authorization": f"Bearer {SECRET}",
            "X-API-Key": SECRET,
            "Cookie": f"session={SECRET}",
            "X-Request-Id": supplied_request_id,
        },
    )
    assert response.status_code == 200
    record = json.loads(stream.getvalue())
    assert record["service.name"] == "test-error-service"
    assert record["http.route"] == "/probe/{resource_id}"
    assert record["http.request.method"] == "POST"
    assert record["http.response.status_code"] == 200
    assert record["log.level"] == "INFO"
    assert isinstance(record["event.duration"], int) and record["event.duration"] > 0
    assert record["trace.id"] == record["http.request.id"] == response.headers["X-Request-Id"]
    assert record["trace.id"] != supplied_request_id
    UUID(record["trace.id"])
    assert SECRET not in stream.getvalue()
    assert "912345" not in stream.getvalue()


def test_problem_ids_are_fresh_and_untrusted_request_ids_are_not_reflected(error_application):
    client, stream = error_application
    first = assert_problem(
        client.get("/failure/missing", headers={"X-Request-Id": SECRET}), 404, "NOT_FOUND"
    )
    second = assert_problem(client.get("/failure/missing"), 404, "NOT_FOUND")
    assert first["traceId"] != second["traceId"]
    assert first["instance"] != second["instance"]
    assert SECRET not in stream.getvalue()


def test_json_formatter_drops_private_extra_fields_and_exception_tracebacks(monkeypatch):
    formatter = JsonFormatter("test-service")
    try:
        raise RuntimeError(f"Database credential={SECRET}")
    except RuntimeError:
        import sys

        exception = sys.exc_info()
    record = logging.LogRecord(
        "test-service", logging.ERROR, __file__, 1, "Safe operation failed", (), exception
    )
    record.password = SECRET
    record.headers = {"Authorization": f"Bearer {SECRET}"}
    record.request_body = SECRET
    record.query_params = SECRET
    record.error_type = "RuntimeError"
    rendered = formatter.format(record)
    assert SECRET not in rendered
    assert json.loads(rendered)["error.type"] == "RuntimeError"

    # Settings may fail before logging is configured, so exception text must be safe itself.
    short_secret = "short-secret"
    for database_url, private_key, expected_location, expected_type in [
        (None, SECRET, ("database_url",), "missing"),
        ("sqlite+pysqlite:///:memory:", short_secret, ("api_key",), "too_short"),
    ]:
        with monkeypatch.context() as environment:
            environment.delenv("DATABASE_URL", raising=False)
            environment.setenv("API_KEY", private_key)
            if database_url is not None:
                environment.setenv("DATABASE_URL", database_url)
            with pytest.raises(ValidationError) as failure:
                Settings(_env_file=None)
        assert [
            (error["loc"], error["type"])
            for error in failure.value.errors(include_input=False, include_context=False)
        ] == [(expected_location, expected_type)]
        for text in (str(failure.value), repr(failure.value)):
            assert SECRET not in text
            assert short_secret not in text
            assert "input_value" not in text
            assert "input_type" not in text


@pytest.fixture
def application_log_stream():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter("test-main-service"))
    application_logger.addHandler(handler)
    try:
        yield stream
    finally:
        application_logger.removeHandler(handler)
        handler.close()


def test_main_application_registers_validation_problems_and_safe_request_logging(
    client, application_log_stream
):
    watchlist = client.post("/watchlists", json={"name": "Games"}).json()
    application_log_stream.seek(0)
    application_log_stream.truncate(0)
    response = client.post(
        f"/watchlists/{watchlist['id']}/items",
        params={"access_token": SECRET},
        json={"gameId": "612", "targetPrice": SECRET},
        headers={"Authorization": SECRET, "Cookie": SECRET, "X-Request-Id": SECRET},
    )
    problem = assert_problem(response, 422, "VALIDATION_ERROR")
    assert problem["errors"]
    record = json.loads(application_log_stream.getvalue())
    assert record["http.route"] == "/watchlists/{watchlist_id}/items"
    assert record["trace.id"] == problem["traceId"]
    assert record["error.code"] == "VALIDATION_ERROR"
    assert SECRET not in application_log_stream.getvalue()


def test_main_application_converts_unhandled_dependency_failure_to_safe_problem(
    client, application_log_stream
):
    from app.api.dependencies import get_dispatcher
    from app.main import app

    class BrokenDispatcher:
        def dispatch(self, usecase):
            raise RuntimeError(f"Connection password={SECRET}")

    previous_override = app.dependency_overrides[get_dispatcher]
    app.dependency_overrides[get_dispatcher] = BrokenDispatcher
    try:
        # The client fixture keeps startup state and isolated database dependencies active.
        instance = TestClient(app, raise_server_exceptions=False, headers=client.headers)
        try:
            response = instance.get("/watchlists")
        finally:
            instance.close()
    finally:
        app.dependency_overrides[get_dispatcher] = previous_override
    problem = assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
    record = json.loads(application_log_stream.getvalue())
    assert record["trace.id"] == problem["traceId"]
    assert record["http.response.status_code"] == 500
    assert record["error.type"] == "RuntimeError"
    assert SECRET not in application_log_stream.getvalue()
