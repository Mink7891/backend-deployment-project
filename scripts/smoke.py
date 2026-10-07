"""Poll DB-aware readiness from the CI machine after deployment."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--expected-source", choices=("cheapshark", "mock"))
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    deadline = time.monotonic() + args.timeout_seconds
    error = "not started"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                args.base_url.rstrip("/") + "/health", timeout=5
            ) as response:
                body = json.load(response)
            if args.expected_source and body.get("priceSource") != args.expected_source:
                raise ValueError("Readiness returned the wrong configured price source")
            print("Smoke passed: HTTP 200 and database-ready health response.")
            return
        except (urllib.error.URLError, ValueError, TimeoutError) as exception:
            error = str(exception)
            time.sleep(2)
    raise SystemExit(f"Smoke failed after {args.timeout_seconds}s: {error}")


if __name__ == "__main__":
    main()
