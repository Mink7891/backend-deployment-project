"""Generate DTOs from the approved contract using datamodel-codegen CLI options only."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
CONTRACT = REPOSITORY / "doc" / "game-radar-api.yaml"
OUTPUT = REPOSITORY / "app" / "schemas" / "game_radar_api.py"


def generation_command(*, check: bool = False) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        str(CONTRACT),
        "--input-file-type",
        "openapi",
        "--output",
        str(OUTPUT),
        "--encoding",
        "utf-8",
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--base-class",
        "app.schemas.base.DTO",
        "--base-class-map",
        json.dumps(
            {
                "CreateWatchlistRequest": "app.schemas.base.CreateWatchlistRequestBase",
                "UpdateItemRequest": "app.schemas.base.UpdateItemRequestBase",
            }
        ),
        "--type-overrides",
        json.dumps(
            {
                "DecimalValue": "decimal.Decimal",
                "MoneyTarget": "app.schemas.types.Money",
            }
        ),
        "--snake-case-field",
        "--allow-population-by-field-name",
        "--use-schema-description",
        "--field-constraints",
        "--use-decimal-for-multiple-of",
        "--enum-field-as-literal",
        "all",
        "--strict-nullable",
        "--extra-fields",
        "forbid",
        "--enable-faux-immutability",
        "--target-python-version",
        "3.12",
        "--use-standard-collections",
        "--use-union-operator",
        "--disable-timestamp",
        "--enable-version-header",
        "--formatters",
        "ruff-check",
        "ruff-format",
        "--wrap-string-literal",
        "--ignore-pyproject",
    ]
    if check:
        command.append("--check")
    return command


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify without changing output")
    arguments = parser.parse_args()
    subprocess.run(generation_command(check=arguments.check), cwd=REPOSITORY, check=True)


if __name__ == "__main__":
    main()
