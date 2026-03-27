"""
Reingestion service - functional core for purging and re-ingesting account data.

Centralises the logic for:
- Planning a purge (collecting transaction IDs and event IDs to remove)
- Executing the purge via proper storage APIs (no raw SQL)
- Clearing the intelligence cache for removed transactions

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt
- sqlite3 (use EventStore and ProjectionBuilder APIs instead)

All dependencies are injected. All functions return data structures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder


@dataclass
class PurgePlan:
    """Plan for purging a single account's data before re-ingestion."""

    account_id: str
    transaction_ids: set[str] = field(default_factory=set)
    event_ids: set[str] = field(default_factory=set)


@dataclass
class PurgeResult:
    """Result of executing a purge plan."""

    events_purged: int
    projections_purged: int
    cache_entries_purged: int


class ReingestionService:
    """
    Service for planning and executing account reingest purges.

    This is the functional core - pure business logic with no direct SQL or
    file I/O beyond the injected storage objects.

    Responsibilities:
    - Collect transaction IDs imported for a given account
    - Collect all event IDs that reference those transactions
    - Purge events via EventStore API
    - Purge projections via ProjectionBuilder API
    - Remove stale intelligence cache entries
    """

    def __init__(
        self,
        event_store: EventStore,
        projection_builder: ProjectionBuilder,
        ledger_data_dir: Path,
        intelligence_cache_path: Path,
    ) -> None:
        self._event_store = event_store
        self._projection_builder = projection_builder
        self._ledger_data_dir = ledger_data_dir
        self._intelligence_cache_path = intelligence_cache_path

    def plan_purge(self, account_id: str) -> PurgePlan:
        """Determine what must be removed to cleanly re-ingest an account.

        Scans the event store for all events that belong to or reference the
        given account's transactions.

        Args:
            account_id: The account to plan a purge for.

        Returns:
            PurgePlan with the transaction IDs and event IDs to remove.
        """
        plan = PurgePlan(account_id=account_id)

        # 1. Collect transaction IDs imported for this account
        import_events = self._event_store.get_events_by_type("TransactionImported")
        for evt in import_events:
            if getattr(evt, "source_account", None) == account_id:
                plan.transaction_ids.add(evt.transaction_id)

        # 2. Collect all event IDs referencing this account or its transactions
        all_events = self._event_store.get_all_events()
        for evt in all_events:
            if getattr(evt, "source_account", None) == account_id:
                plan.event_ids.add(evt.event_id)
                continue

            evt_txn_id = getattr(evt, "transaction_id", None)
            if evt_txn_id and evt_txn_id in plan.transaction_ids:
                plan.event_ids.add(evt.event_id)
                continue

            for attr in (
                "transaction_id_1",
                "transaction_id_2",
                "primary_transaction_id",
                "duplicate_transaction_id",
                "original_transaction_id",
                "new_transaction_id",
            ):
                ref_id = getattr(evt, attr, None)
                if ref_id and ref_id in plan.transaction_ids:
                    plan.event_ids.add(evt.event_id)
                    break

        return plan

    def execute_purge(self, plan: PurgePlan) -> PurgeResult:
        """Execute a purge plan, removing events, projections, and cache entries.

        Args:
            plan: The PurgePlan produced by plan_purge().

        Returns:
            PurgeResult with counts of what was removed.
        """
        # 1. Purge events via EventStore API
        events_purged = self._event_store.delete_events(plan.event_ids)

        # 2. Purge projections via ProjectionBuilder API
        projections_purged = self._projection_builder.delete_account_projections(plan.account_id)
        self._projection_builder.reset_metadata()

        # 3. Purge intelligence cache entries
        cache_entries_purged = self._purge_intelligence_cache(plan.transaction_ids)

        return PurgeResult(
            events_purged=events_purged,
            projections_purged=projections_purged,
            cache_entries_purged=cache_entries_purged,
        )

    def _purge_intelligence_cache(self, txn_ids: set[str]) -> int:
        """Remove cached intelligence entries for the given transaction IDs.

        Args:
            txn_ids: Set of transaction IDs whose cache entries should be removed.

        Returns:
            Number of entries removed.
        """
        if not self._intelligence_cache_path.exists():
            return 0

        try:
            data = json.loads(self._intelligence_cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return 0

        original_count = len(data)
        data = {k: v for k, v in data.items() if k not in txn_ids}
        removed = original_count - len(data)

        if removed > 0:
            self._intelligence_cache_path.write_text(json.dumps(data), encoding="utf-8")

        return removed


__all__ = [
    "PurgePlan",
    "PurgeResult",
    "ReingestionService",
]
