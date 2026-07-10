"""Specs for gilt.storage.sqlite_connection — connection lifecycle helper."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from gilt.storage.sqlite_connection import connect


class DescribeConnect:
    @pytest.fixture
    def db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        yield path
        if path.exists():
            path.unlink()

    def it_should_close_the_connection_on_success(self, db_path):
        with connect(db_path) as conn:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            conn.commit()

        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def it_should_close_the_connection_when_the_body_raises(self, db_path):
        conn_ref = None
        try:
            with connect(db_path) as conn:
                conn_ref = conn
                raise ValueError("intentional")
        except ValueError:
            pass

        with pytest.raises(sqlite3.ProgrammingError):
            conn_ref.execute("SELECT 1")
