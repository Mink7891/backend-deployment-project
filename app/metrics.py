import time

from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

HTTP_REQUESTS = Counter(
    "gameradar_http_requests_total", "Completed HTTP requests", ["method", "route", "status"]
)
HTTP_DURATION = Histogram(
    "gameradar_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20),
)
DATABASE_READY = Gauge("gameradar_database_ready", "Database connection and schema are ready")


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            matched_route = request.scope.get("route")
            route = getattr(matched_route, "path", "__unmatched__")
            method = (
                request.method
                if request.method in {"GET", "POST", "PATCH", "PUT", "DELETE", "HEAD", "OPTIONS"}
                else "OTHER"
            )
            HTTP_REQUESTS.labels(method, route, str(status)).inc()
            HTTP_DURATION.labels(method, route).observe(time.perf_counter() - started)
