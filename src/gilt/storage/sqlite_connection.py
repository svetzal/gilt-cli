"""Shared SQLite connection lifecycle helper."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection and close it on exit, even if the body raises."""
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


__all__ = ["connect"]
