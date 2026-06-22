"""Write-side event application for budget projections."""

from __future__ import annotations

import sqlite3

from gilt.model.events import BudgetCreated, BudgetDeleted, BudgetUpdated, Event


def apply_budget_events(conn: sqlite3.Connection, events: list[Event]) -> int:
    """Apply a list of budget events to the projections database.

    Returns:
        Number of events processed
    """
    processed = 0
    for event in events:
        if isinstance(event, BudgetCreated):
            _apply_budget_created(conn, event)
        elif isinstance(event, BudgetUpdated):
            _apply_budget_updated(conn, event)
        elif isinstance(event, BudgetDeleted):
            _apply_budget_deleted(conn, event)
        processed += 1
    conn.commit()
    return processed


def _apply_budget_created(conn: sqlite3.Connection, event: BudgetCreated) -> None:
    cursor = conn.execute(
        "SELECT budget_id FROM budget_projections WHERE budget_id = ?", (event.budget_id,)
    )
    if cursor.fetchone():
        return  # Idempotent: already exists

    conn.execute(
        """
        INSERT INTO budget_projections (
            budget_id, category, subcategory, amount, period_type,
            start_date, currency, is_deleted, created_at, updated_at,
            last_event_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """,
        (
            event.budget_id,
            event.category,
            event.subcategory,
            float(event.amount),
            event.period_type,
            event.start_date,
            event.currency,
            event.event_timestamp.isoformat(),
            event.event_timestamp.isoformat(),
            event.event_id,
        ),
    )

    conn.execute(
        """
        INSERT INTO budget_history (
            budget_id, category, subcategory, amount, period_type,
            start_date, end_date, currency, event_type, event_timestamp,
            event_id
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, 'BudgetCreated', ?, ?)
        """,
        (
            event.budget_id,
            event.category,
            event.subcategory,
            float(event.amount),
            event.period_type,
            event.start_date,
            event.currency,
            event.event_timestamp.isoformat(),
            event.event_id,
        ),
    )


def _resolve_updated_values(
    event: BudgetUpdated,
    current_amount: float,
    current_period: str,
    current_start: str,
) -> tuple[float, str, str]:
    new_amount = float(event.new_amount) if event.new_amount else current_amount
    new_period = event.new_period_type if event.new_period_type else current_period
    new_start = event.new_start_date if event.new_start_date else current_start
    return new_amount, new_period, new_start


def _update_budget_history(
    conn: sqlite3.Connection,
    event: BudgetUpdated,
    new_amount: float,
    new_period: str,
    new_start: str,
) -> None:
    conn.execute(
        """
        UPDATE budget_history
        SET end_date = ?
        WHERE budget_id = ? AND end_date IS NULL
        """,
        (
            event.event_timestamp.isoformat(),
            event.budget_id,
        ),
    )

    conn.execute(
        """
        INSERT INTO budget_history (
            budget_id, category, subcategory, amount, period_type,
            start_date, end_date, currency, event_type, event_timestamp,
            event_id
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, 'BudgetUpdated', ?, ?)
        """,
        (
            event.budget_id,
            event.category,
            event.subcategory,
            new_amount,
            new_period,
            new_start,
            event.currency,
            event.event_timestamp.isoformat(),
            event.event_id,
        ),
    )


def _apply_budget_updated(conn: sqlite3.Connection, event: BudgetUpdated) -> None:
    cursor = conn.execute(
        """
        SELECT amount, period_type, start_date
        FROM budget_projections
        WHERE budget_id = ?
        """,
        (event.budget_id,),
    )
    row = cursor.fetchone()

    if not row:
        return  # Budget doesn't exist yet, skip

    current_amount, current_period, current_start = row
    new_amount, new_period, new_start = _resolve_updated_values(
        event, current_amount, current_period, current_start
    )

    conn.execute(
        """
        UPDATE budget_projections
        SET amount = ?,
            period_type = ?,
            start_date = ?,
            updated_at = ?,
            last_event_id = ?
        WHERE budget_id = ?
        """,
        (
            new_amount,
            new_period,
            new_start,
            event.event_timestamp.isoformat(),
            event.event_id,
            event.budget_id,
        ),
    )

    _update_budget_history(conn, event, new_amount, new_period, new_start)


def _apply_budget_deleted(conn: sqlite3.Connection, event: BudgetDeleted) -> None:
    conn.execute(
        """
        UPDATE budget_projections
        SET is_deleted = 1,
            updated_at = ?,
            last_event_id = ?
        WHERE budget_id = ?
        """,
        (
            event.event_timestamp.isoformat(),
            event.event_id,
            event.budget_id,
        ),
    )

    conn.execute(
        """
        UPDATE budget_history
        SET end_date = ?
        WHERE budget_id = ? AND end_date IS NULL
        """,
        (
            event.event_timestamp.isoformat(),
            event.budget_id,
        ),
    )

    conn.execute(
        """
        INSERT INTO budget_history (
            budget_id, category, subcategory, amount, period_type,
            start_date, end_date, currency, event_type, event_timestamp,
            event_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'BudgetDeleted', ?, ?)
        """,
        (
            event.budget_id,
            event.category,
            event.subcategory,
            float(event.final_amount),
            event.final_period_type,
            event.final_start_date,
            event.event_timestamp.isoformat(),
            event.currency,
            event.event_timestamp.isoformat(),
            event.event_id,
        ),
    )


__all__ = ["apply_budget_events"]
