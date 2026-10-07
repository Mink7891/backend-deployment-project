from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection

from app.config import get_settings


def make_engine(url: str):
    options = {"pool_pre_ping": True, "pool_recycle": 1800}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    database_engine = create_engine(url, **options)
    if url.startswith("sqlite"):

        @event.listens_for(database_engine, "connect")
        def set_sqlite_foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return database_engine


engine = make_engine(get_settings().database_url)


def get_connection() -> Generator[Connection]:
    """Open and close a connection; transaction boundaries belong to handlers."""
    with engine.connect() as connection:
        yield connection
