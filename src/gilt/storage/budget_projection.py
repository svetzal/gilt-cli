"""
Budget projection builder for event sourcing.

This module rebuilds the current and historical state of budgets from the
immutable event log. Budget projections enable time-travel queries like
"what was my transportation budget in October 2024?"

The implementation is split into cohesive collaborator modules:
- budget_projection_schema.py  — schema creation (DDL)
- budget_projection_reducer.py — event-application (write side)
- budget_projection_queries.py — read-model queries and BudgetProjection type

This module keeps the BudgetProjectionBuilder facade (preserving the public
API used across services and GUI) and re-exports all public names.

Privacy: All processing is local-only. No network I/O.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from gilt.storage.budget_projection_queries import (
    BudgetProjection,
    get_active_budgets,
    get_budget,
    get_budget_history,
    get_budgets_at_date,
)
from gilt.storage.budget_projection_reducer import apply_budget_events
from gilt.storage.budget_projection_schema import ensure_budget_projection_schema
from gilt.storage.event_store import EventStore
from gilt.storage.sqlite_connection import connect


class BudgetProjectionBuilder:
    """Builds budget projections from event stream."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        with connect(db_path) as conn:
            ensure_budget_projection_schema(conn)

    def build_from_scratch(self, event_store: EventStore) -> int:
        """Build all budget projections from event store.

        Deletes existing projections and replays all events to reconstruct
        current state and history.

        Returns:
            Number of events processed
        """
        with connect(self.db_path) as conn:
            conn.execute("DELETE FROM budget_projections")
            conn.execute("DELETE FROM budget_history")
            conn.commit()

            events = event_store.get_events_by_type("BudgetCreated")
            events.extend(event_store.get_events_by_type("BudgetUpdated"))
            events.extend(event_store.get_events_by_type("BudgetDeleted"))
            events.sort(key=lambda e: e.event_timestamp)

            return apply_budget_events(conn, events)

    def get_budget(self, budget_id: str) -> BudgetProjection | None:
        """Retrieve a single budget projection."""
        return get_budget(self.db_path, budget_id)

    def get_active_budgets(
        self, category: str | None = None, as_of_date: date | None = None
    ) -> list[BudgetProjection]:
        """Retrieve all active (non-deleted) budgets.

        Args:
            category: Optional category filter
            as_of_date: Optional date to get historical budget state
        """
        if as_of_date:
            return get_budgets_at_date(self.db_path, as_of_date, category)
        return get_active_budgets(self.db_path, category)

    def get_budgets_at_date(
        self, target_date: date, category: str | None = None
    ) -> list[BudgetProjection]:
        """Time-travel query: get budget state as it was on a specific date."""
        return get_budgets_at_date(self.db_path, target_date, category)

    def get_budget_history(self, budget_id: str) -> list[dict]:
        """Get complete history of a budget's changes."""
        return get_budget_history(self.db_path, budget_id)


__all__ = ["BudgetProjection", "BudgetProjectionBuilder"]
