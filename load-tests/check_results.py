"""Fail CI when a JMeter CSV result is invalid or exceeds the agreed SLO."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path


class InvalidResults(ValueError):
    """The input cannot demonstrate a successful load test."""


def percentile(values: list[int], quantile: float) -> int:
    """Nearest-rank percentile; preserve individual slow requests in small runs."""
    ordered = sorted(values)
    if not ordered:
        raise InvalidResults("No request samples were recorded")
    return ordered[max(0, math.ceil(len(ordered) * quantile) - 1)]


def summarize(path: Path) -> dict:
    durations: list[int] = []
    starts: list[int] = []
    ends: list[int] = []
    errors = 0
    operations: dict[str, dict[str, int]] = {}
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"timeStamp", "elapsed", "label", "success"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise InvalidResults(f"CSV must contain columns: {', '.join(sorted(required))}")
            for line, row in enumerate(reader, start=2):
                if None in row or any(row.get(column) is None for column in required):
                    raise InvalidResults(f"Malformed CSV row at line {line}")
                try:
                    timestamp = int(row["timeStamp"])
                    elapsed = int(row["elapsed"])
                except (TypeError, ValueError) as exc:
                    raise InvalidResults(f"Invalid timeStamp/elapsed at line {line}") from exc
                success = row["success"].strip().lower()
                label = row["label"].strip()
                if timestamp < 0 or elapsed < 0 or success not in {"true", "false"} or not label:
                    raise InvalidResults(f"Invalid request sample at line {line}")
                durations.append(elapsed)
                starts.append(timestamp)
                ends.append(timestamp + elapsed)
                failed = int(success == "false")
                errors += failed
                operation = operations.setdefault(label, {"samples": 0, "errors": 0})
                operation["samples"] += 1
                operation["errors"] += failed
    except (OSError, UnicodeError, csv.Error) as exc:
        raise InvalidResults(f"Cannot read results: {exc}") from exc
    if not durations:
        raise InvalidResults("No request samples were recorded")
    duration_seconds = (max(ends) - min(starts)) / 1000
    if duration_seconds <= 0:
        raise InvalidResults("Observed test duration must be greater than zero")
    return {
        "samples": len(durations),
        "errors": errors,
        "error_rate": errors / len(durations),
        "duration_seconds": round(duration_seconds, 3),
        "throughput_rps": round(len(durations) / duration_seconds, 3),
        "p90_ms": percentile(durations, 0.90),
        "p95_ms": percentile(durations, 0.95),
        "p99_ms": percentile(durations, 0.99),
        "operations": operations,
    }


def evaluate(summary: dict, max_error_rate: float, p95_ms: float) -> list[str]:
    violations = []
    if summary["error_rate"] > max_error_rate:
        violations.append(f"error_rate {summary['error_rate']:.6f} > {max_error_rate:.6f}")
    if summary["p95_ms"] > p95_ms:
        violations.append(f"p95_ms {summary['p95_ms']} > {p95_ms:g}")
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="JMeter CSV .jtl file")
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--p95-ms", type=float, default=1000)
    args = parser.parse_args(argv)
    if not math.isfinite(args.max_error_rate) or not 0 <= args.max_error_rate <= 1:
        parser.error("--max-error-rate must be a finite value between 0 and 1")
    if not math.isfinite(args.p95_ms) or args.p95_ms <= 0:
        parser.error("--p95-ms must be finite and greater than zero")
    try:
        summary = summarize(args.results)
    except InvalidResults as exc:
        print(json.dumps({"passed": False, "invalid_results": str(exc)}), file=sys.stderr)
        return 2
    violations = evaluate(summary, args.max_error_rate, args.p95_ms)
    summary.update(
        passed=not violations,
        thresholds={"max_error_rate": args.max_error_rate, "p95_ms": args.p95_ms},
        violations=violations,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return int(bool(violations))


if __name__ == "__main__":
    raise SystemExit(main())
