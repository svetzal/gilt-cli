"""DDL and migrations for budget projection tables."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def ensure_budget_projection_schema(db_path: Path) -> None:
    """Create budget projection tables and indexes if they don't exist."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS budget_projections (
                budget_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                subcategory TEXT,
                amount REAL NOT NULL,
                period_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'CAD',
                is_deleted INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_event_id TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_budget_proj_category
            ON budget_projections(category, subcategory)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_budget_proj_start_date
            ON budget_projections(start_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_budget_proj_active
            ON budget_projections(is_deleted, start_date)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS budget_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                budget_id TEXT NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT,
                amount REAL NOT NULL,
                period_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                currency TEXT NOT NULL DEFAULT 'CAD',
                event_type TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                event_id TEXT NOT NULL,
                FOREIGN KEY (budget_id) REFERENCES budget_projections(budget_id)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_budget_hist_budget
            ON budget_history(budget_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_budget_hist_dates
            ON budget_history(start_date, end_date)
        """)

        conn.commit()
    finally:
        conn.close()


__all__ = ["ensure_budget_projection_schema"]
