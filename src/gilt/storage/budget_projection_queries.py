"""Read-model queries and domain type for budget projections."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


class BudgetProjection:
    """Represents the current state of a budget.

    Derived from budget events; a materialized view at a specific point in time.
    """

    def __init__(
        self,
        budget_id: str,
        category: str,
        subcategory: str | None,
        amount: Decimal,
        period_type: str,
        start_date: str,
        currency: str,
        is_deleted: bool,
        created_at: datetime,
        updated_at: datetime,
        last_event_id: str,
    ):
        self.budget_id = budget_id
        self.category = category
        self.subcategory = subcategory
        self.amount = amount
        self.period_type = period_type
        self.start_date = start_date
        self.currency = currency
        self.is_deleted = is_deleted
        self.created_at = created_at
        self.updated_at = updated_at
        self.last_event_id = last_event_id

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "budget_id": self.budget_id,
            "category": self.category,
            "subcategory": self.subcategory,
            "amount": str(self.amount),
            "period_type": self.period_type,
            "start_date": self.start_date,
            "currency": self.currency,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_event_id": self.last_event_id,
        }


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
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM budget_projections WHERE budget_id = ?", (budget_id,))
        row = cursor.fetchone()
        return _row_to_budget_projection(row) if row else None
    finally:
        conn.close()


def get_active_budgets(db_path: Path, category: str | None = None) -> list[BudgetProjection]:
    """Retrieve all active (non-deleted) budgets, optionally filtered by category."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
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
    finally:
        conn.close()


def get_budgets_at_date(
    db_path: Path, target_date: date, category: str | None = None
) -> list[BudgetProjection]:
    """Time-travel query: get budget state as it was on a specific date.

    Enables queries like "what was my transportation budget in October 2024?"
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
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
    finally:
        conn.close()


def get_budget_history(db_path: Path, budget_id: str) -> list[dict]:
    """Get complete history of a budget's changes, ordered by timestamp."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            """
            SELECT * FROM budget_history
            WHERE budget_id = ?
            ORDER BY event_timestamp
            """,
            (budget_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


__all__ = [
    "BudgetProjection",
    "get_budget",
    "get_active_budgets",
    "get_budgets_at_date",
    "get_budget_history",
]
