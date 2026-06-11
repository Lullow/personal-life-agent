"""Table definitions and database initialisation."""

from life_agent.db.database import get_connection

TASKS_TABLE = """\
CREATE TABLE IF NOT EXISTS tasks (
    id               TEXT PRIMARY KEY,
    title            TEXT    NOT NULL,
    description      TEXT,
    priority         TEXT    NOT NULL DEFAULT 'medium',
    status           TEXT    NOT NULL DEFAULT 'pending',
    category         TEXT    NOT NULL DEFAULT 'other',
    estimated_minutes INTEGER,
    due_date         TEXT,
    created_at       TEXT    NOT NULL,
    updated_at       TEXT
);
"""

EVENTS_TABLE = """\
CREATE TABLE IF NOT EXISTS events (
    id               TEXT PRIMARY KEY,
    title            TEXT    NOT NULL,
    description      TEXT,
    category         TEXT    NOT NULL DEFAULT 'other',
    start_time       TEXT    NOT NULL,
    end_time         TEXT,
    location         TEXT,
    created_at       TEXT    NOT NULL
);
"""

ACTIVITIES_TABLE = """\
CREATE TABLE IF NOT EXISTS activities (
    id               TEXT PRIMARY KEY,
    title            TEXT    NOT NULL,
    activity_type    TEXT    NOT NULL DEFAULT 'other',
    duration_minutes INTEGER,
    logged_at        TEXT    NOT NULL,
    notes            TEXT,
    created_at       TEXT    NOT NULL
);
"""


def init_db(db_path: str | None = None) -> None:
    """Create all tables if they do not already exist."""
    conn = get_connection(db_path)
    try:
        conn.execute(TASKS_TABLE)
        conn.execute(EVENTS_TABLE)
        conn.execute(ACTIVITIES_TABLE)
        conn.commit()
    finally:
        conn.close()
