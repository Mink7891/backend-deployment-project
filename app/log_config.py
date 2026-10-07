"""ECS-shaped JSON logs with explicit safe context and distinct output streams."""

import json
import logging
import sys
from datetime import UTC, datetime

_CONTEXT_FIELDS = {
    "trace_id": "trace.id",
    "request_id": "http.request.id",
    "method": "http.request.method",
    "route": "http.route",
    "status_code": "http.response.status_code",
    "duration_ns": "event.duration",
    "error_code": "error.code",
    "error_type": "error.type",
}


class BelowWarningFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.WARNING


class JsonFormatter(logging.Formatter):
    def __init__(self, service_name: str, *, safe_message: str | None = None):
        super().__init__()
        self.service_name = service_name
        self.safe_message = safe_message

    def format(self, record: logging.LogRecord) -> str:
        event = {
            "@timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "ecs.version": "8.11.0",
            "log.level": record.levelname,
            "message": self.safe_message if self.safe_message is not None else record.getMessage(),
            "service.name": self.service_name,
        }
        for field, output in _CONTEXT_FIELDS.items():
            value = getattr(record, field, None)
            if isinstance(value, (str, int, float, bool)):
                event[output] = value
        # Deliberately omit exception repr/traceback and all non-allowlisted extra fields.
        return json.dumps(event, ensure_ascii=False, allow_nan=False)


logger = logging.getLogger("gameradar")
logger.addHandler(logging.NullHandler())


class _ForwardToApplication(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        logger.handle(record)


def _configure_streams(target: logging.Logger, formatter: JsonFormatter) -> None:
    for handler in list(target.handlers):
        target.removeHandler(handler)
        handler.close()
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.addFilter(BelowWarningFilter())
    stdout_handler.setFormatter(formatter)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)
    target.addHandler(stdout_handler)
    target.addHandler(stderr_handler)
    target.setLevel(logging.INFO)
    target.propagate = False


def configure_logging(service_name: str = "gameradar") -> logging.Logger:
    """Configure app/server logs once without access URLs, traceback text or duplicates."""
    _configure_streams(logger, JsonFormatter(service_name))
    app_logger = logging.getLogger("app")
    for handler in list(app_logger.handlers):
        app_logger.removeHandler(handler)
        handler.close()
    app_logger.addHandler(_ForwardToApplication())
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    # Uvicorn lifespan can put an already-formatted traceback into record.msg. Dropping
    # exc_info alone would not protect secrets, so server events have a fixed safe message.
    _configure_streams(
        logging.getLogger("uvicorn.error"),
        JsonFormatter(service_name, safe_message="ASGI server event"),
    )
    logging.getLogger("uvicorn.access").disabled = True
    return logger
