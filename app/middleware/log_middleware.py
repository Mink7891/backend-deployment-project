"""Streaming ASGI request logging without reading payloads or private request data."""

import logging
from time import perf_counter_ns
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.log_config import logger as application_logger

_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp, logger: logging.Logger | None = None):
        self.app = app
        self.logger = logger or application_logger

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        trace_id = str(uuid4())
        state["trace_id"] = trace_id
        state["request_id"] = trace_id
        started = perf_counter_ns()
        status = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", trace_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            state["error_type"] = type(exc).__name__
            state.setdefault("error_code", "INTERNAL_SERVER_ERROR")
            raise
        finally:
            route = getattr(scope.get("route"), "path", "__unmatched__")
            method = scope.get("method", "OTHER")
            context = {
                "trace_id": trace_id,
                "request_id": trace_id,
                "method": method if method in _METHODS else "OTHER",
                "route": route,
                "status_code": status,
                "duration_ns": perf_counter_ns() - started,
                "error_code": state.get("error_code"),
                "error_type": state.get("error_type"),
            }
            level = (
                logging.ERROR
                if status >= 500
                else (logging.WARNING if status >= 400 else logging.INFO)
            )
            self.logger.log(level, "HTTP request completed", extra=context)
