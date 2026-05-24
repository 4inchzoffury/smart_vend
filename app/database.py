from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import settings


def _normalize_db_url(url: str) -> str:
    """Force Postgres URLs onto the psycopg (v3) driver.

    Render hands back a ``postgresql://…`` connection string, and SQLAlchemy maps a
    bare ``postgresql://`` to psycopg2 — which we don't install. Rewrite the scheme
    to ``postgresql+psycopg://`` so psycopg 3 is used. (``postgres://``, the legacy
    Heroku-style alias SQLAlchemy 2.0 no longer accepts, is normalized too.)
    SQLite URLs pass through unchanged.
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


DATABASE_URL = _normalize_db_url(settings.database_url)
_IS_SQLITE = DATABASE_URL.startswith("sqlite")

if _IS_SQLITE:
    # Local dev: let FastAPI's threadpool share the connection and wait on locks.
    # Both args are SQLite-specific and would error on the Postgres driver.
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _set_wal_mode(dbapi_conn: Any, _record: Any) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
else:
    # Postgres (Render): pool_pre_ping discards connections the managed DB or its
    # proxy dropped, avoiding stale-connection errors after idle periods. WAL and
    # the SQLite connect_args do not apply here.
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
