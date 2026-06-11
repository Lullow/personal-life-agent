"""SQLite connection management and database bootstrap."""

import sqlite3
from pathlib import Path

from life_agent.config import get_settings


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection, creating the parent directory if needed.

    Parameters
    ----------
    db_path:
        Filesystem path for the database file.  Falls back to the
        configured ``Settings.db_path`` when *None*.
    """
    path = db_path or get_settings().db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    """Create all tables if they do not already exist.

    Delegates to :func:`life_agent.db.schema.init_db` (imported lazily to
    avoid a circular import at module level).
    """
    from life_agent.db.schema import init_db as _init_db

    _init_db(db_path)
