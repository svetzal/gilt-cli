"""
Event store implementation using SQLite.

This module provides an append-only event store for the event sourcing
architecture. Events are immutable and stored in order, forming the
source of truth for system state.

Privacy: Event store is local-only SQLite. Never transmit events over
networks as they contain sensitive financial data.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TypeVar

from gilt.model.events import (
    BudgetCreated,
    BudgetDeleted,
    BudgetUpdated,
    CategorizationRuleCreated,
    DuplicateConfirmed,
    DuplicateRejected,
    DuplicateSuggested,
    Event,
    PromptUpdated,
    TransactionCategorized,
    TransactionDescriptionObserved,
    TransactionEnriched,
    TransactionImported,
)

# Type variable for generic event types
TEvent = TypeVar("TEvent", bound=Event)

# Map event types to classes for deserialization
EVENT_TYPE_MAP: dict[str, type[Event]] = {
    "TransactionImported": TransactionImported,
    "TransactionDescriptionObserved": TransactionDescriptionObserved,
    "DuplicateSuggested": DuplicateSuggested,
    "DuplicateConfirmed": DuplicateConfirmed,
    "DuplicateRejected": DuplicateRejected,
    "TransactionCategorized": TransactionCategorized,
    "TransactionEnriched": TransactionEnriched,
    "CategorizationRuleCreated": CategorizationRuleCreated,
    "BudgetCreated": BudgetCreated,
    "BudgetUpdated": BudgetUpdated,
    "BudgetDeleted": BudgetDeleted,
    "PromptUpdated": PromptUpdated,
}


class EventStore:
    """Append-only event store using SQLite.

    The event store is the single source of truth for all state changes
    in the system. Events are immutable and ordered sequentially.

    Design:
    - Append-only: events never modified or deleted
    - Sequential: events have sequence numbers for ordering
    - Queryable: events can be retrieved by aggregate, type, or sequence
    - Local-only: SQLite database file, no network I/O

    Usage:
        store = EventStore("data/events.db")
        event = TransactionImported(...)
        store.append_event(event)
        events = store.get_events("transaction", "txn-123")
    """

    def __init__(self, db_path: str):
        """Initialize event store with SQLite database.

        Args:
            db_path: Path to SQLite database file. Will be created if doesn't exist.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema if not exists."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Core event log (append-only)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    event_timestamp TEXT NOT NULL,
                    aggregate_type TEXT,
                    aggregate_id TEXT,
                    event_data TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_type
                ON events(event_type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_timestamp
                ON events(event_timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_aggregate
                ON events(aggregate_type, aggregate_id)
            """)

            # Event sequence tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_sequence (
                    sequence_number INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events(event_id)
                )
            """)

            conn.commit()
        finally:
            conn.close()

    def append_event(self, event: Event) -> None:
        """Append an event to the store.

        Args:
            event: Event to append (must be a subclass of Event)

        Events are immutable after appending. The event is serialized to JSON
        and stored with its metadata.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Serialize event data (full event as JSON)
            event_data = event.model_dump_json()
            metadata_json = json.dumps(event.metadata) if event.metadata else None

            # Insert into events table
            cursor.execute(
                """
                INSERT INTO events (
                    event_id, event_type, event_timestamp,
                    aggregate_type, aggregate_id, event_data, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event.event_id,
                    event.event_type,
                    event.event_timestamp.isoformat(),
                    event.aggregate_type,
                    event.aggregate_id,
                    event_data,
                    metadata_json,
                ),
            )

            # Track sequence
            cursor.execute(
                """
                INSERT INTO event_sequence (event_id) VALUES (?)
            """,
                (event.event_id,),
            )

            conn.commit()
        finally:
            conn.close()

    def get_all_events(self) -> list[Event]:
        """Retrieve all events in sequence order.

        Returns:
            List of events in the order they were appended.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.event_data
                FROM events e
                JOIN event_sequence es ON e.event_id = es.event_id
                ORDER BY es.sequence_number
            """)

            events = []
            for (event_data,) in cursor.fetchall():
                event = self._deserialize_event(event_data)
                events.append(event)

            return events
        finally:
            conn.close()

    def get_events(self, aggregate_type: str, aggregate_id: str) -> list[Event]:
        """Retrieve all events for a specific aggregate.

        Args:
            aggregate_type: Type of aggregate (e.g., "transaction", "duplicate")
            aggregate_id: ID of the aggregate

        Returns:
            List of events for the aggregate in sequence order.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT e.event_data
                FROM events e
                JOIN event_sequence es ON e.event_id = es.event_id
                WHERE e.aggregate_type = ? AND e.aggregate_id = ?
                ORDER BY es.sequence_number
            """,
                (aggregate_type, aggregate_id),
            )

            events = []
            for (event_data,) in cursor.fetchall():
                event = self._deserialize_event(event_data)
                events.append(event)

            return events
        finally:
            conn.close()

    def get_events_by_type(self, event_type: str) -> list[Event]:
        """Retrieve all events of a specific type.

        Args:
            event_type: Type of event (e.g., "TransactionImported")

        Returns:
            List of events of that type in sequence order.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT e.event_data
                FROM events e
                JOIN event_sequence es ON e.event_id = es.event_id
                WHERE e.event_type = ?
                ORDER BY es.sequence_number
            """,
                (event_type,),
            )

            events = []
            for (event_data,) in cursor.fetchall():
                event = self._deserialize_event(event_data)
                events.append(event)

            return events
        finally:
            conn.close()

    def get_events_since(self, sequence_number: int) -> list[Event]:
        """Retrieve events after a specific sequence number.

        Useful for incremental projection updates.

        Args:
            sequence_number: Get events after this sequence (exclusive)

        Returns:
            List of events after the sequence number.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT e.event_data
                FROM events e
                JOIN event_sequence es ON e.event_id = es.event_id
                WHERE es.sequence_number > ?
                ORDER BY es.sequence_number
            """,
                (sequence_number,),
            )

            events = []
            for (event_data,) in cursor.fetchall():
                event = self._deserialize_event(event_data)
                events.append(event)

            return events
        finally:
            conn.close()

    def get_latest_sequence_number(self) -> int:
        """Get the latest sequence number in the store.

        Returns:
            Latest sequence number, or 0 if store is empty.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(sequence_number) FROM event_sequence
            """)
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0
        finally:
            conn.close()

    def _deserialize_event(self, event_data: str) -> Event:
        """Deserialize event from JSON.

        Args:
            event_data: JSON string of event data

        Returns:
            Deserialized event object of the appropriate type.
        """
        data = json.loads(event_data)
        event_type = data.get("event_type")

        event_class = EVENT_TYPE_MAP.get(event_type)
        if not event_class:
            raise ValueError(f"Unknown event type: {event_type}")

        return event_class.model_validate_json(event_data)


__all__ = ["EventStore"]
