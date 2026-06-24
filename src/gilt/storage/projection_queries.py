"""
Read-model queries for transaction projections.

Module-level functions that query the projection database. Each opens and closes
its own connection, matching the existing per-call connect/close pattern.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CategoryHistoryRow:
    """Aggregated categorization history for a description pattern."""

    category: str | None
    subcategory: str | None
    count: int
    total: float
    min_amount: float
    max_amount: float
    latest_date: str


def get_transaction(db_path: Path, transaction_id: str) -> dict | None:
    """Retrieve a single transaction projection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT * FROM transaction_projections WHERE transaction_id = ?", (transaction_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_transactions(db_path: Path, include_duplicates: bool = False) -> list[dict]:
    """Retrieve all transaction projections."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if include_duplicates:
            cursor = conn.execute(
                "SELECT * FROM transaction_projections ORDER BY transaction_date, account_id"
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM transaction_projections
                WHERE is_duplicate = 0
                ORDER BY transaction_date, account_id
                """
            )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_current_sequence(db_path: Path) -> int:
    """Get the last event sequence number that was processed."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("SELECT value FROM projection_metadata WHERE key = 'last_sequence'")
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def get_distinct_account_ids(db_path: Path) -> list[str]:
    """Return sorted list of non-duplicate account IDs from the projections database."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            "SELECT DISTINCT account_id FROM transaction_projections "
            "WHERE is_duplicate = 0 ORDER BY account_id"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def find_category_history(
    db_path: Path,
    pattern: str,
    *,
    account_id: str | None = None,
    include_uncategorized: bool = False,
    limit: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[CategoryHistoryRow]:
    """Aggregate categorization history for transactions matching a description pattern."""
    conn = sqlite3.connect(db_path)
    try:
        sql_parts = [
            "SELECT category, subcategory,",
            "       COUNT(*) AS cnt,",
            "       SUM(amount) AS total,",
            "       MIN(amount) AS min_amt,",
            "       MAX(amount) AS max_amt,",
            "       MAX(transaction_date) AS latest",
            "FROM transaction_projections",
            "WHERE is_duplicate = 0",
            "  AND canonical_description LIKE ? COLLATE NOCASE",
        ]
        params: list = [f"%{pattern}%"]

        if account_id is not None:
            sql_parts.append("  AND account_id = ?")
            params.append(account_id)

        if not include_uncategorized:
            sql_parts.append("  AND category IS NOT NULL")

        if date_from is not None:
            sql_parts.append("  AND transaction_date >= ?")
            params.append(date_from)

        if date_to is not None:
            sql_parts.append("  AND transaction_date <= ?")
            params.append(date_to)

        sql_parts.append("GROUP BY category, subcategory")
        sql_parts.append("ORDER BY cnt DESC")

        sql_parts.append("LIMIT ?")
        params.append(limit)

        sql = "\n".join(sql_parts)
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        return [
            CategoryHistoryRow(
                category=row[0],
                subcategory=row[1],
                count=row[2],
                total=row[3],
                min_amount=row[4],
                max_amount=row[5],
                latest_date=row[6],
            )
            for row in rows
        ]
    finally:
        conn.close()
