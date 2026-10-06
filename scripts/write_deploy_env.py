"""Write CI credentials to mode-0600 env files without printing secret values."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from urllib.parse import quote


def write_environment(path: Path, values: dict[str, str]) -> None:
    for key, value in values.items():
        if any(character in value for character in "\r\n\0"):
            raise ValueError(f"{key} contains an unsupported control character")
    # Compose single quotes suppress interpolation of $ in credentials.
    content = "".join(
        f"{key}='{value.replace(chr(39), chr(92) + chr(39))}'\n" for key, value in values.items()
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    path.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", type=Path, default=Path(".deploy.env"))
    parser.add_argument("--load", type=Path, default=Path(".deploy.load.env"))
    args = parser.parse_args()
    required = ("API_KEY", "POSTGRES_PASSWORD", "GRAFANA_PASSWORD", "IMAGE_REPOSITORY", "IMAGE_TAG")
    for name in required:
        if not os.environ.get(name):
            raise ValueError(f"Missing credential/configuration {name}")
    if len(os.environ["API_KEY"]) < 16:
        raise ValueError("API_KEY must contain at least 16 characters")
    if not re.fullmatch(r"[a-zA-Z0-9_@.-]+", os.environ.get("REGISTRY_USERNAME", "registry-user")):
        raise ValueError("Registry username contains unsupported SSH command characters")
    user = os.environ.get("POSTGRES_USER", "radar")
    database = os.environ.get("POSTGRES_DB", "radar")
    for value in (user, database):
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", value):
            raise ValueError("Use lowercase alphanumeric PostgreSQL identifiers")
    password = quote(os.environ["POSTGRES_PASSWORD"], safe="")
    values = {
        "API_KEY": os.environ["API_KEY"],
        "POSTGRES_USER": user,
        "POSTGRES_PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "POSTGRES_DB": database,
        "DATABASE_URL": f"postgresql+psycopg://{user}:{password}@db:5432/{database}",
        "IMAGE_REPOSITORY": os.environ["IMAGE_REPOSITORY"],
        "IMAGE_TAG": os.environ["IMAGE_TAG"],
        "PRICE_SOURCE": "cheapshark",
        "APP_BIND_ADDRESS": "0.0.0.0",
        "APP_PORT": os.environ.get("PROD_PORT", "8000"),
        "GRAFANA_USER": os.environ.get("GRAFANA_USER", "admin"),
        "GRAFANA_PASSWORD": os.environ["GRAFANA_PASSWORD"],
        "REFRESH_INTERVAL_SECONDS": "3600",
        "BACKUP_INTERVAL_SECONDS": os.environ.get("BACKUP_INTERVAL_SECONDS", "86400"),
        "BACKUP_RETENTION_COUNT": os.environ.get("BACKUP_RETENTION_COUNT", "7"),
        "PROMETHEUS_PORT": "9090",
        "GRAFANA_PORT": "3000",
    }
    write_environment(args.production, values)
    load_values = values | {
        "PRICE_SOURCE": "mock",
        "APP_PORT": os.environ.get("LOAD_PORT", "8001"),
        "LOAD_POSTGRES_DB": "radar_load",
        "LOAD_DATABASE_URL": f"postgresql+psycopg://{user}:{password}@db:5432/radar_load",
        "REFRESH_INTERVAL_SECONDS": "30",
        "PROMETHEUS_PORT": "9091",
        "GRAFANA_PORT": "3001",
    }
    write_environment(args.load, load_values)


if __name__ == "__main__":
    main()
