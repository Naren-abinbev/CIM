from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _get_database_url() -> str:
    """
    Return the SQLAlchemy database URL.

    Environment override: SQLALCHEMY_DATABASE_URL

    Default: SQLite at SQLITE_DATABASE_PATH
    """
    settings = get_settings()
    return "sqlite:///" + settings.sqlite_database_path


def _ensure_sqlite_parent(database_url: str) -> None:
    """
    Create the parent directory for a file-based SQLite database.
    """
    if not database_url.startswith("sqlite:///"):
        return

    # sqlite:///relative/path.db  or  sqlite:////absolute/path.db
    db_path = database_url.removeprefix("sqlite:///")

    if db_path and not db_path.startswith(":"):  # skip :memory:
        parent = Path(db_path).parent
        parent.mkdir(parents=True, exist_ok=True)


def _configure_sqlite(
    dbapi_connection: object,
    _connection_record: object,
) -> None:
    """
    Enable SQLite foreign keys and WAL mode per connection.
    """
    cursor = dbapi_connection.cursor()

    cursor.execute("PRAGMA foreign_keys=ON")

    # WAL improves concurrent read/write behaviour on SQLite.
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
    except Exception:
        # Some in-memory/test configurations do not support WAL.
        logger.debug("WAL mode not available for SQLite.", exc_info=True)

    cursor.execute("PRAGMA busy_timeout=5000")

    cursor.close()


database_url = _get_database_url()

_ensure_sqlite_parent(database_url)

# check_same_thread=False is required because FastAPI
# executes sync dependencies in a threadpool while the
# engine may be used from other threads as well.
engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    future=True,
)

if database_url.startswith("sqlite"):
    event.listen(
        engine,
        "connect",
        _configure_sqlite,
    )

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def init_db() -> None:
    """
    Create all tables if they do not exist.

    This is safe to call on every application startup.
    It never drops or alters existing tables.
    """
    # Import models so they are registered on Base.metadata.
    from backend.database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    logger.info(
        "Database initialized from %s",
        database_url,
    )


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a request-scoped session.

    The session is always closed after the request completes.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()