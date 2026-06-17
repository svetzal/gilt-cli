"""
Transaction projection builder for event sourcing.

This module rebuilds the current state of transactions from the immutable
event log. Projections are materialized views that can be rebuilt at any
time by replaying events.

The implementation is split into cohesive collaborator modules:
- projection_schema.py  — schema creation and migration
- projection_reducer.py — event-application (write side)
- projection_queries.py — read-model queries (read side)
- duplicate_normalization.py — pure duplicate-group repair logic

This module keeps the ProjectionBuilder facade (preserving the public API
used across CLI commands, services, and GUI) and re-exports all public names.

Privacy: All processing is local-only. No network I/O.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from gilt.storage.duplicate_normalization import (
    DuplicateCorrection,
    DuplicateGroupState,
    build_duplicate_corrections,
    find_root_primary,
    normalize_duplicate_groups,
)
from gilt.storage.event_store import EventStore
from gilt.storage.projection_queries import (
    CategoryHistoryRow,
    find_category_history,
    get_all_transactions,
    get_current_sequence,
    get_distinct_account_ids,
    get_transaction,
)
from gilt.storage.projection_reducer import apply_events
from gilt.storage.projection_schema import ensure_projection_schema


class ProjectionBuilder:
    """Builds transaction projections from event stream."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        conn = sqlite3.connect(self.db_path)
        try:
            ensure_projection_schema(conn)
        finally:
            conn.close()

    def build_from_scratch(self, event_store: EventStore) -> int:
        """Build all projections from event store.

        Deletes existing projections and replays all events to reconstruct
        current state. This is safe because events are immutable.

        Returns:
            Number of events processed
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM transaction_projections")
            conn.execute("DELETE FROM projection_metadata")
            conn.commit()

            events = event_store.get_all_events()
            processed = apply_events(conn, events, start_sequence=0)
            normalize_duplicate_groups(conn)
            conn.commit()
            return processed
        finally:
            conn.close()

    def build_incremental(self, event_store: EventStore) -> int:
        """Apply only new events since last build.

        Returns:
            Number of new events processed
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT value FROM projection_metadata WHERE key = 'last_sequence'"
            )
            row = cursor.fetchone()
            last_sequence = int(row[0]) if row else 0

            events = event_store.get_events_since(last_sequence)
            if not events:
                return 0

            processed = apply_events(conn, events, start_sequence=last_sequence)
            normalize_duplicate_groups(conn)
            conn.commit()
            return processed
        finally:
            conn.close()

    def delete_account_projections(self, account_id: str) -> int:
        """Delete all projection rows for a given account.

        Returns:
            Number of rows deleted.
        """
        if not self.db_path.exists():
            return 0
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM transaction_projections WHERE account_id = ?",
                (account_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def reset_metadata(self) -> None:
        """Clear projection metadata so the next incremental rebuild replays all events."""
        if not self.db_path.exists():
            return
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM projection_metadata")
            conn.commit()
        finally:
            conn.close()

    # --- Read-model delegations ---

    def get_transaction(self, transaction_id: str) -> dict | None:
        return get_transaction(self.db_path, transaction_id)

    def get_all_transactions(self, include_duplicates: bool = False) -> list[dict]:
        return get_all_transactions(self.db_path, include_duplicates)

    def get_current_sequence(self) -> int:
        return get_current_sequence(self.db_path)

    def get_distinct_account_ids(self) -> list[str]:
        return get_distinct_account_ids(self.db_path)

    def find_category_history(
        self,
        pattern: str,
        *,
        account_id: str | None = None,
        include_uncategorized: bool = False,
        limit: int = 10,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[CategoryHistoryRow]:
        return find_category_history(
            self.db_path,
            pattern,
            account_id=account_id,
            include_uncategorized=include_uncategorized,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
        )


__all__ = [
    "CategoryHistoryRow",
    "DuplicateCorrection",
    "DuplicateGroupState",
    "ProjectionBuilder",
    "find_root_primary",
    "build_duplicate_corrections",
]
