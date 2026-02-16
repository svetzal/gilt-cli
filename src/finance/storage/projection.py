"""
Transaction projection builder for event sourcing.

This module rebuilds the current state of transactions from the immutable
event log. Projections are materialized views that can be rebuilt at any
time by replaying events.

Key Features:
- Rebuild projections from scratch or incrementally
- Track description evolution via TransactionDescriptionObserved events
- Store canonical description (most recent) and complete history
- Derive current state for queries without scanning event log

Privacy: All processing is local-only. No network I/O.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import json

from finance.model.events import (
    Event,
    TransactionImported,
    TransactionDescriptionObserved,
    TransactionCategorized,
    DuplicateConfirmed,
    DuplicateRejected,
)
from finance.storage.event_store import EventStore


class ProjectionBuilder:
    """Builds transaction projections from event stream."""

    def __init__(self, db_path: Path):
        """Initialize projection builder with database path.

        Args:
            db_path: Path to SQLite database for projections
        """
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create projection tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transaction_projections (
                    transaction_id TEXT PRIMARY KEY,
                    transaction_date TEXT NOT NULL,
                    canonical_description TEXT NOT NULL,
                    description_history TEXT,  -- JSON array of all observed descriptions
                    amount REAL NOT NULL,
                    currency TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    category TEXT,
                    subcategory TEXT,
                    counterparty TEXT,
                    notes TEXT,
                    source_file TEXT,
                    is_duplicate INTEGER DEFAULT 0,
                    primary_transaction_id TEXT,
                    last_event_id TEXT,
                    projection_version INTEGER DEFAULT 1,
                    FOREIGN KEY (primary_transaction_id)
                        REFERENCES transaction_projections(transaction_id)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_txn_proj_date
                ON transaction_projections(transaction_date)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_txn_proj_account
                ON transaction_projections(account_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_txn_proj_category
                ON transaction_projections(category, subcategory)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS projection_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            conn.commit()
        finally:
            conn.close()

    def rebuild_from_scratch(self, event_store: EventStore) -> int:
        """Rebuild all projections from event store.

        Deletes existing projections and replays all events to reconstruct
        current state. This is safe because events are immutable.

        Args:
            event_store: Event store to replay events from

        Returns:
            Number of events processed
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Clear existing projections
            conn.execute("DELETE FROM transaction_projections")
            conn.execute("DELETE FROM projection_metadata")
            conn.commit()

            # Replay all events
            events = event_store.get_all_events()
            return self._apply_events(conn, events, start_sequence=0)
        finally:
            conn.close()

    def rebuild_incremental(self, event_store: EventStore) -> int:
        """Apply only new events since last rebuild.

        More efficient than full rebuild for large event stores.

        Args:
            event_store: Event store to read new events from

        Returns:
            Number of new events processed
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Get last processed sequence number
            cursor = conn.execute(
                "SELECT value FROM projection_metadata WHERE key = 'last_sequence'"
            )
            row = cursor.fetchone()
            last_sequence = int(row[0]) if row else 0

            # Get new events only
            events = event_store.get_events_since(last_sequence)
            if not events:
                return 0

            return self._apply_events(conn, events, start_sequence=last_sequence)
        finally:
            conn.close()

    def _apply_events(
        self,
        conn: sqlite3.Connection,
        events: List[Event],
        start_sequence: int
    ) -> int:
        """Apply a list of events to projections.

        Args:
            conn: Database connection
            events: Events to apply
            start_sequence: Starting sequence number for metadata update

        Returns:
            Number of events processed
        """
        processed = 0

        for event in events:
            if isinstance(event, TransactionImported):
                self._apply_transaction_imported(conn, event)
            elif isinstance(event, TransactionDescriptionObserved):
                self._apply_description_observed(conn, event)
            elif isinstance(event, TransactionCategorized):
                self._apply_transaction_categorized(conn, event)
            elif isinstance(event, DuplicateConfirmed):
                self._apply_duplicate_confirmed(conn, event)
            elif isinstance(event, DuplicateRejected):
                self._apply_duplicate_rejected(conn, event)
            # Other event types handled in future phases

            processed += 1

        # Update last processed sequence
        if events:
            last_event_seq = start_sequence + processed
            conn.execute(
                """
                INSERT OR REPLACE INTO projection_metadata (key, value)
                VALUES ('last_sequence', ?)
                """,
                (str(last_event_seq),)
            )

        conn.commit()
        return processed

    def _apply_transaction_imported(
        self,
        conn: sqlite3.Connection,
        event: TransactionImported
    ) -> None:
        """Apply TransactionImported event to projection."""
        # Check if transaction already exists (idempotent)
        cursor = conn.execute(
            "SELECT transaction_id FROM transaction_projections WHERE transaction_id = ?",
            (event.transaction_id,)
        )
        if cursor.fetchone():
            return  # Already imported

        # Create new projection
        description_history = json.dumps([event.raw_description])

        conn.execute(
            """
            INSERT INTO transaction_projections (
                transaction_id, transaction_date, canonical_description,
                description_history, amount, currency, account_id,
                source_file, last_event_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.transaction_id,
                event.transaction_date,
                event.raw_description,
                description_history,
                float(event.amount),
                event.currency,
                event.source_account,
                event.source_file,
                event.event_id,
            )
        )

    def _apply_description_observed(
        self,
        conn: sqlite3.Connection,
        event: TransactionDescriptionObserved
    ) -> None:
        """Apply TransactionDescriptionObserved event to projection.

        When a description changes, we:
        1. Update the canonical description to the new one
        2. Add the new description to the history
        3. Link the new transaction_id to the original (treat as same transaction)
        """
        # Get original transaction
        cursor = conn.execute(
            """
            SELECT canonical_description, description_history
            FROM transaction_projections
            WHERE transaction_id = ?
            """,
            (event.original_transaction_id,)
        )
        row = cursor.fetchone()

        if not row:
            # Original transaction not in projection yet, skip
            return

        canonical_desc, history_json = row
        history = json.loads(history_json) if history_json else []

        # Add new description to history if not already present
        if event.new_description not in history:
            history.append(event.new_description)

        # Update original transaction with new canonical description
        conn.execute(
            """
            UPDATE transaction_projections
            SET canonical_description = ?,
                description_history = ?,
                last_event_id = ?
            WHERE transaction_id = ?
            """,
            (
                event.new_description,
                json.dumps(history),
                event.event_id,
                event.original_transaction_id,
            )
        )

        # If new transaction_id exists as separate projection, mark it as duplicate
        # This handles the case where it was imported before we detected the change
        cursor = conn.execute(
            "SELECT transaction_id FROM transaction_projections WHERE transaction_id = ?",
            (event.new_transaction_id,)
        )
        if cursor.fetchone():
            conn.execute(
                """
                UPDATE transaction_projections
                SET is_duplicate = 1,
                    primary_transaction_id = ?,
                    last_event_id = ?
                WHERE transaction_id = ?
                """,
                (
                    event.original_transaction_id,
                    event.event_id,
                    event.new_transaction_id,
                )
            )

    def _apply_transaction_categorized(
        self,
        conn: sqlite3.Connection,
        event: TransactionCategorized
    ) -> None:
        """Apply TransactionCategorized event to projection."""
        conn.execute(
            """
            UPDATE transaction_projections
            SET category = ?,
                subcategory = ?,
                last_event_id = ?
            WHERE transaction_id = ?
            """,
            (
                event.category,
                event.subcategory,
                event.event_id,
                event.transaction_id,
            )
        )

    def _apply_duplicate_confirmed(
        self,
        conn: sqlite3.Connection,
        event: DuplicateConfirmed
    ) -> None:
        """Apply DuplicateConfirmed event to projection.

        Marks the duplicate transaction with is_duplicate flag and links it
        to the primary transaction. Updates the primary transaction's canonical
        description to the user's preferred choice.
        """
        # Update primary transaction with canonical description
        conn.execute(
            """
            UPDATE transaction_projections
            SET canonical_description = ?,
                last_event_id = ?
            WHERE transaction_id = ?
            """,
            (
                event.canonical_description,
                event.event_id,
                event.primary_transaction_id,
            )
        )

        # Mark duplicate transaction
        conn.execute(
            """
            UPDATE transaction_projections
            SET is_duplicate = 1,
                primary_transaction_id = ?,
                last_event_id = ?
            WHERE transaction_id = ?
            """,
            (
                event.primary_transaction_id,
                event.event_id,
                event.duplicate_transaction_id,
            )
        )

    def _apply_duplicate_rejected(
        self,
        conn: sqlite3.Connection,
        event: DuplicateRejected
    ) -> None:
        """Apply DuplicateRejected event to projection.

        Records the rejection for potential ML training but doesn't change
        projection state. Both transactions remain separate and active.
        """
        # Update last_event_id to track that we processed this feedback
        conn.execute(
            """
            UPDATE transaction_projections
            SET last_event_id = ?
            WHERE transaction_id IN (?, ?)
            """,
            (
                event.event_id,
                event.transaction_id_1,
                event.transaction_id_2,
            )
        )

    def get_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Retrieve a single transaction projection.

        Args:
            transaction_id: Transaction ID to retrieve

        Returns:
            Transaction data as dict, or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT * FROM transaction_projections WHERE transaction_id = ?",
                (transaction_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_transactions(
        self,
        include_duplicates: bool = False
    ) -> List[Dict]:
        """Retrieve all transaction projections.

        Args:
            include_duplicates: Whether to include transactions marked as duplicates

        Returns:
            List of transaction data as dicts
        """
        conn = sqlite3.connect(self.db_path)
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

    def get_current_sequence(self) -> int:
        """Get the last event sequence number that was processed.

        Returns:
            Last processed sequence number, or 0 if no events have been processed
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT value FROM projection_metadata WHERE key = 'last_sequence'"
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()


__all__ = ["ProjectionBuilder"]
