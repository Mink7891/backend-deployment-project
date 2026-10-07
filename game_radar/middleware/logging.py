"""JSON-логирование и middleware access-логов с trace_id."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_logger = logging.getLogger("game_radar.request")


class JsonLogFormatter(logging.Formatter):
    """Форматирует лог-записи в одну JSON-строку."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra_fields = getattr(record, "extra_fields", None)
        if extra_fields:
            payload.update(extra_fields)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    """Настраивает JSON-логирование на root-логгере."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level.upper())

    # httpx/httpcore логируют на INFO полный URL запроса; приглушаем до WARNING.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # Access-лог ведёт RequestLoggingMiddleware; стандартный вывод uvicorn его дублирует.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Генерирует trace_id на запрос и логирует его в JSON-формате.

    Заголовки и тела запросов не логируются: в X-API-Key передаётся секрет.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        started_at = time.perf_counter()
        status_code = 500
        failed = False
        try:
            response = await call_next(request)
        except Exception:
            failed = True
            raise
        else:
            status_code = response.status_code
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            extra_fields = {
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            }
            error_code = getattr(request.state, "error_code", None)
            if error_code is not None:
                extra_fields["error_code"] = error_code
            if failed:
                request_logger.error(
                    "request_failed", exc_info=True, extra={"extra_fields": extra_fields}
                )
            else:
                request_logger.info("request_handled", extra={"extra_fields": extra_fields})
