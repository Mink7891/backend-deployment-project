"""Export selected load-sandbox Prometheus time series before its volumes are removed.

Run with its source on stdin in the app container so Prometheus stays loopback-only
on the deployment host. This uses Python's standard library and prints no secrets.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request

QUERIES = {
    "requests_per_second_by_route": (
        'sum by (route) (rate(gameradar_http_requests_total{route!~"/health|/metrics"}[1m]))'
    ),
    "p95_seconds_by_route": (
        "histogram_quantile(0.95, sum by (le, route) "
        '(rate(gameradar_http_request_duration_seconds_bucket{route!~"/health|/metrics"}[1m])))'
    ),
    "http_5xx_requests_per_second": (
        'sum(rate(gameradar_http_requests_total{status=~"5..",route!~"/health|/metrics"}[1m]))'
        " or vector(0)"
    ),
    "postgres_ready": "pg_up",
    "api_scrape_ready": 'up{job="game-radar"}',
    "database_connections": 'pg_stat_database_numbackends{datname!~"template.*"}',
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prometheus", default="http://prometheus:9090")
    parser.add_argument("--window-seconds", type=int, default=900)
    args = parser.parse_args()
    if args.window_seconds <= 0:
        raise ValueError("The export window must be positive")
    end = int(time.time())
    output = {
        "scope": "isolated mock load environment",
        "start_unix_seconds": end - args.window_seconds,
        "end_unix_seconds": end,
        "step_seconds": 10,
        "series": {},
    }
    for name, query in QUERIES.items():
        parameters = urllib.parse.urlencode(
            {"query": query, "start": end - args.window_seconds, "end": end, "step": 10}
        )
        url = args.prometheus.rstrip("/") + "/api/v1/query_range?" + parameters
        with urllib.request.urlopen(url, timeout=15) as response:
            result = json.load(response)
        if result.get("status") != "success":
            raise ValueError(f"Prometheus could not export {name}")
        output["series"][name] = {"query": query, "result": result["data"]["result"]}
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
