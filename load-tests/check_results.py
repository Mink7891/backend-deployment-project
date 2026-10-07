"""Проверка результатов JMeter: доля ошибок и 95-й перцентиль времени ответа.

Использование:
    python3 load-tests/check_results.py reports/load.jtl --max-error-rate 0.01 --p95-ms 1000
Завершается с кодом 1, если хотя бы один порог превышен — это останавливает пайплайн.
"""

import argparse
import csv
import math
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jtl", help="CSV-файл результатов JMeter (-l)")
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--p95-ms", type=int, default=1000)
    args = parser.parse_args()

    with open(args.jtl, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        print("JTL пустой: запросы не выполнялись")
        return 1

    elapsed = sorted(int(row["elapsed"]) for row in rows)
    errors = sum(row["success"].lower() != "true" for row in rows)
    error_rate = errors / len(rows)
    p95 = elapsed[max(0, math.ceil(0.95 * len(elapsed)) - 1)]

    print(f"Запросов: {len(rows)}, ошибок: {errors} ({error_rate:.2%}), p95: {p95} мс")
    failed = False
    if error_rate > args.max_error_rate:
        print(f"ОШИБКА: доля ошибок выше {args.max_error_rate:.0%}")
        failed = True
    if p95 > args.p95_ms:
        print(f"ОШИБКА: p95 выше {args.p95_ms} мс")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
