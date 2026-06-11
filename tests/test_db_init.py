"""Tests for database initialisation."""

import sqlite3
import tempfile
from pathlib import Path

from life_agent.db.schema import init_db


def _table_names(db_path: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def test_init_db_creates_tables():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        init_db(db_path)
        tables = _table_names(db_path)
        assert "tasks" in tables
        assert "events" in tables
        assert "activities" in tables


def test_init_db_is_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        init_db(db_path)
        init_db(db_path)
        tables = _table_names(db_path)
        assert "tasks" in tables


def test_init_db_creates_parent_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "sub" / "nested" / "test.db")
        init_db(db_path)
        assert Path(db_path).exists()


def test_init_db_importable_from_database_module():
    from life_agent.db.database import init_db as init_from_database

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        init_from_database(db_path)
        tables = _table_names(db_path)
        assert "tasks" in tables
        assert "events" in tables
        assert "activities" in tables
