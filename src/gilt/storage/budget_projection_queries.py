"""Read-model queries and domain type for budget projections."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from gilt.storage.sqlite_connection import connect


class BudgetProjection(BaseModel):
    """Represents the current state of a budget.

    Derived from budget events; a materialized view at a specific point in time.
    """

    budget_id: str
    category: str
    subcategory: str | None
    amount: Decimal
    period_type: str
    start_date: str
    currency: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    last_event_id: str

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode="json")


def _row_to_budget_projection(row: sqlite3.Row) -> BudgetProjection:
    return BudgetProjection(
        budget_id=row["budget_id"],
        category=row["category"],
        subcategory=row["subcategory"],
        amount=Decimal(str(row["amount"])),
        period_type=row["period_type"],
        start_date=row["start_date"],
        currency=row["currency"],
        is_deleted=bool(row["is_deleted"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        last_event_id=row["last_event_id"],
    )


def get_budget(db_path: Path, budget_id: str) -> BudgetProjection | None:
    """Retrieve a single budget projection."""
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM budget_projections WHERE budget_id = ?", (budget_id,))
        row = cursor.fetchone()
        return _row_to_budget_projection(row) if row else None


def get_active_budgets(db_path: Path, category: str | None = None) -> list[BudgetProjection]:
    """Retrieve all active (non-deleted) budgets, optionally filtered by category."""
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if category:
            cursor = conn.execute(
                """
                SELECT * FROM budget_projections
                WHERE is_deleted = 0 AND category = ?
                ORDER BY category, subcategory
                """,
                (category,),
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM budget_projections
                WHERE is_deleted = 0
                ORDER BY category, subcategory
                """
            )
        return [_row_to_budget_projection(row) for row in cursor.fetchall()]


def get_budgets_at_date(
    db_path: Path, target_date: date, category: str | None = None
) -> list[BudgetProjection]:
    """Time-travel query: get budget state as it was on a specific date.

    Enables queries like "what was my transportation budget in October 2024?"
    """
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        target_iso = target_date.isoformat()

        if category:
            cursor = conn.execute(
                """
                SELECT
                    budget_id, category, subcategory, amount, period_type,
                    start_date, currency, event_timestamp, event_id
                FROM budget_history
                WHERE category = ?
                  AND start_date <= ?
                  AND (end_date IS NULL OR end_date > ?)
                  AND event_type != 'BudgetDeleted'
                """,
                (category, target_iso, target_iso),
            )
        else:
            cursor = conn.execute(
                """
                SELECT
                    budget_id, category, subcategory, amount, period_type,
                    start_date, currency, event_timestamp, event_id
                FROM budget_history
                WHERE start_date <= ?
                  AND (end_date IS NULL OR end_date > ?)
                  AND event_type != 'BudgetDeleted'
                """,
                (target_iso, target_iso),
            )

        results = []
        for row in cursor.fetchall():
            results.append(
                BudgetProjection(
                    budget_id=row["budget_id"],
                    category=row["category"],
                    subcategory=row["subcategory"],
                    amount=Decimal(str(row["amount"])),
                    period_type=row["period_type"],
                    start_date=row["start_date"],
                    currency=row["currency"],
                    is_deleted=False,
                    created_at=datetime.fromisoformat(row["event_timestamp"]),
                    updated_at=datetime.fromisoformat(row["event_timestamp"]),
                    last_event_id=row["event_id"],
                )
            )
        return results


def get_budget_history(db_path: Path, budget_id: str) -> list[dict]:
    """Get complete history of a budget's changes, ordered by timestamp."""
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT * FROM budget_history
            WHERE budget_id = ?
            ORDER BY event_timestamp
            """,
            (budget_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


__all__ = [
    "BudgetProjection",
    "get_budget",
    "get_active_budgets",
    "get_budgets_at_date",
    "get_budget_history",
]
