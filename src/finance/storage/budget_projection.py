"""
Budget projection builder for event sourcing.

This module rebuilds the current and historical state of budgets from the
immutable event log. Budget projections enable time-travel queries like
"what was my transportation budget in October 2024?"

Key Features:
- Rebuild budget state at any point in time
- Track budget lifecycle (created, updated, deleted)
- Support historical queries for budget analysis
- Store both current state and complete audit trail

Privacy: All processing is local-only. No network I/O.
"""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, date

from finance.model.events import (
    Event,
    BudgetCreated,
    BudgetUpdated,
    BudgetDeleted,
)
from finance.storage.event_store import EventStore


class BudgetProjection:
    """Represents the current state of a budget.

    This is derived from budget events and represents the materialized
    view at a specific point in time.
    """

    def __init__(
        self,
        budget_id: str,
        category: str,
        subcategory: Optional[str],
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

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'budget_id': self.budget_id,
            'category': self.category,
            'subcategory': self.subcategory,
            'amount': str(self.amount),
            'period_type': self.period_type,
            'start_date': self.start_date,
            'currency': self.currency,
            'is_deleted': self.is_deleted,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_event_id': self.last_event_id,
        }


class BudgetProjectionBuilder:
    """Builds budget projections from event stream."""

    def __init__(self, db_path: Path):
        """Initialize budget projection builder with database path.

        Args:
            db_path: Path to SQLite database for projections
        """
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create budget projection tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
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

            # Budget history table for time-travel queries
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

    def rebuild_from_scratch(self, event_store: EventStore) -> int:
        """Rebuild all budget projections from event store.

        Deletes existing projections and replays all events to reconstruct
        current state and history.

        Args:
            event_store: Event store to replay events from

        Returns:
            Number of events processed
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Clear existing projections
            conn.execute("DELETE FROM budget_projections")
            conn.execute("DELETE FROM budget_history")
            conn.commit()

            # Replay budget events
            events = event_store.get_events_by_type("BudgetCreated")
            events.extend(event_store.get_events_by_type("BudgetUpdated"))
            events.extend(event_store.get_events_by_type("BudgetDeleted"))

            # Sort by timestamp to maintain causal order
            events.sort(key=lambda e: e.event_timestamp)

            return self._apply_events(conn, events)
        finally:
            conn.close()

    def rebuild_incremental(self, event_store: EventStore, last_event_id: str) -> int:
        """Apply only new budget events since last rebuild.

        Args:
            event_store: Event store to read new events from
            last_event_id: ID of last processed event

        Returns:
            Number of new events processed
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Get new budget events
            all_events = []
            for event_type in ["BudgetCreated", "BudgetUpdated", "BudgetDeleted"]:
                all_events.extend(event_store.get_events_by_type(event_type))

            # Filter to events after last_event_id
            # Sort by timestamp
            all_events.sort(key=lambda e: e.event_timestamp)

            # Find index of last processed event
            start_idx = 0
            for i, event in enumerate(all_events):
                if event.event_id == last_event_id:
                    start_idx = i + 1
                    break

            new_events = all_events[start_idx:]
            if not new_events:
                return 0

            return self._apply_events(conn, new_events)
        finally:
            conn.close()

    def _apply_events(
        self,
        conn: sqlite3.Connection,
        events: List[Event]
    ) -> int:
        """Apply a list of budget events to projections.

        Args:
            conn: Database connection
            events: Events to apply

        Returns:
            Number of events processed
        """
        processed = 0

        for event in events:
            if isinstance(event, BudgetCreated):
                self._apply_budget_created(conn, event)
            elif isinstance(event, BudgetUpdated):
                self._apply_budget_updated(conn, event)
            elif isinstance(event, BudgetDeleted):
                self._apply_budget_deleted(conn, event)

            processed += 1

        conn.commit()
        return processed

    def _apply_budget_created(
        self,
        conn: sqlite3.Connection,
        event: BudgetCreated
    ) -> None:
        """Apply BudgetCreated event to projection."""
        # Check if budget already exists (idempotent)
        cursor = conn.execute(
            "SELECT budget_id FROM budget_projections WHERE budget_id = ?",
            (event.budget_id,)
        )
        if cursor.fetchone():
            return  # Already exists

        # Create new projection
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
            )
        )

        # Add to history
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
            )
        )

    def _apply_budget_updated(
        self,
        conn: sqlite3.Connection,
        event: BudgetUpdated
    ) -> None:
        """Apply BudgetUpdated event to projection."""
        # Get current budget state
        cursor = conn.execute(
            """
            SELECT amount, period_type, start_date
            FROM budget_projections
            WHERE budget_id = ?
            """,
            (event.budget_id,)
        )
        row = cursor.fetchone()

        if not row:
            # Budget doesn't exist yet, skip
            return

        current_amount, current_period, current_start = row

        # Calculate new values (use current if not updated)
        new_amount = float(event.new_amount) if event.new_amount else current_amount
        new_period = event.new_period_type if event.new_period_type else current_period
        new_start = event.new_start_date if event.new_start_date else current_start

        # Update projection
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
            )
        )

        # Close previous history entry
        conn.execute(
            """
            UPDATE budget_history
            SET end_date = ?
            WHERE budget_id = ? AND end_date IS NULL
            """,
            (
                event.event_timestamp.isoformat(),
                event.budget_id,
            )
        )

        # Add new history entry
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
            )
        )

    def _apply_budget_deleted(
        self,
        conn: sqlite3.Connection,
        event: BudgetDeleted
    ) -> None:
        """Apply BudgetDeleted event to projection.

        Soft delete - marks budget as deleted but preserves data.
        """
        # Update projection (soft delete)
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
            )
        )

        # Close history entry
        conn.execute(
            """
            UPDATE budget_history
            SET end_date = ?
            WHERE budget_id = ? AND end_date IS NULL
            """,
            (
                event.event_timestamp.isoformat(),
                event.budget_id,
            )
        )

        # Add deletion to history
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
            )
        )

    def get_budget(self, budget_id: str) -> Optional[BudgetProjection]:
        """Retrieve a single budget projection.

        Args:
            budget_id: Budget ID to retrieve

        Returns:
            BudgetProjection or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT * FROM budget_projections WHERE budget_id = ?",
                (budget_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            return BudgetProjection(
                budget_id=row['budget_id'],
                category=row['category'],
                subcategory=row['subcategory'],
                amount=Decimal(str(row['amount'])),
                period_type=row['period_type'],
                start_date=row['start_date'],
                currency=row['currency'],
                is_deleted=bool(row['is_deleted']),
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at']),
                last_event_id=row['last_event_id'],
            )
        finally:
            conn.close()

    def get_active_budgets(
        self,
        category: Optional[str] = None,
        as_of_date: Optional[date] = None
    ) -> List[BudgetProjection]:
        """Retrieve all active (non-deleted) budgets.

        Args:
            category: Optional category filter
            as_of_date: Optional date to get historical budget state

        Returns:
            List of active budget projections
        """
        if as_of_date:
            return self.get_budgets_at_date(as_of_date, category)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            if category:
                cursor = conn.execute(
                    """
                    SELECT * FROM budget_projections
                    WHERE is_deleted = 0 AND category = ?
                    ORDER BY category, subcategory
                    """,
                    (category,)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM budget_projections
                    WHERE is_deleted = 0
                    ORDER BY category, subcategory
                    """
                )

            results = []
            for row in cursor.fetchall():
                results.append(BudgetProjection(
                    budget_id=row['budget_id'],
                    category=row['category'],
                    subcategory=row['subcategory'],
                    amount=Decimal(str(row['amount'])),
                    period_type=row['period_type'],
                    start_date=row['start_date'],
                    currency=row['currency'],
                    is_deleted=bool(row['is_deleted']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    last_event_id=row['last_event_id'],
                ))

            return results
        finally:
            conn.close()

    def get_budgets_at_date(
        self,
        target_date: date,
        category: Optional[str] = None
    ) -> List[BudgetProjection]:
        """Time-travel query: get budget state as it was on a specific date.

        This enables queries like "what was my transportation budget in October 2024?"

        Args:
            target_date: Date to query budget state for
            category: Optional category filter

        Returns:
            List of budget projections active at that date
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            target_iso = target_date.isoformat()

            # Query history table for budgets active on target date
            if category:
                query = """
                    SELECT
                        budget_id, category, subcategory, amount, period_type,
                        start_date, currency, event_timestamp, event_id
                    FROM budget_history
                    WHERE category = ?
                      AND start_date <= ?
                      AND (end_date IS NULL OR end_date > ?)
                      AND event_type != 'BudgetDeleted'
                """
                cursor = conn.execute(query, (category, target_iso, target_iso))
            else:
                query = """
                    SELECT
                        budget_id, category, subcategory, amount, period_type,
                        start_date, currency, event_timestamp, event_id
                    FROM budget_history
                    WHERE start_date <= ?
                      AND (end_date IS NULL OR end_date > ?)
                      AND event_type != 'BudgetDeleted'
                """
                cursor = conn.execute(query, (target_iso, target_iso))

            results = []
            for row in cursor.fetchall():
                # Construct BudgetProjection from historical data
                results.append(BudgetProjection(
                    budget_id=row['budget_id'],
                    category=row['category'],
                    subcategory=row['subcategory'],
                    amount=Decimal(str(row['amount'])),
                    period_type=row['period_type'],
                    start_date=row['start_date'],
                    currency=row['currency'],
                    is_deleted=False,  # Wouldn't be in results if deleted at this time
                    created_at=datetime.fromisoformat(row['event_timestamp']),
                    updated_at=datetime.fromisoformat(row['event_timestamp']),
                    last_event_id=row['event_id'],
                ))

            return results
        finally:
            conn.close()

    def get_budget_history(self, budget_id: str) -> List[Dict]:
        """Get complete history of a budget's changes.

        Args:
            budget_id: Budget ID to get history for

        Returns:
            List of historical states ordered by timestamp
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                """
                SELECT * FROM budget_history
                WHERE budget_id = ?
                ORDER BY event_timestamp
                """,
                (budget_id,)
            )

            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


__all__ = ["BudgetProjection", "BudgetProjectionBuilder"]
