"""
Categorization persistence service - functional core for persisting categorization changes.

Orchestrates the three-step write pattern:
1. Emit TransactionCategorized events to the event store
2. Update per-account ledger CSV files
3. Rebuild projections incrementally

This eliminates the duplicated inline helpers in ingest.py, infer_rules.py,
categorize.py, and recategorize.py.

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from gilt.model.account import TransactionGroup
from gilt.model.events import TransactionCategorized
from gilt.model.ledger_io import dump_ledger_csv, load_ledger_csv
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder


@dataclass
class CategorizationUpdate:
    """A single categorization change to apply to a transaction."""

    transaction_id: str
    account_id: str
    category: str
    subcategory: str | None
    source: str
    confidence: float


@dataclass
class CategorizationPersistenceResult:
    """Result of a categorization persistence operation."""

    transactions_updated: int
    events_emitted: int
    accounts_written: list[str] = field(default_factory=list)


def write_categorizations_to_csv(
    updates: list[CategorizationUpdate],
    ledger_data_dir: Path,
) -> None:
    """Write category updates directly to per-account CSV ledger files.

    Groups updates by account_id, loads each ledger, applies the updates in memory,
    and writes the file back. Does NOT emit events or rebuild projections.

    Silently skips accounts whose ledger file does not exist.

    Args:
        updates: Categorization changes to apply.
        ledger_data_dir: Directory containing per-account CSV ledger files.
    """
    by_account: dict[str, list[CategorizationUpdate]] = {}
    for update in updates:
        by_account.setdefault(update.account_id, []).append(update)

    for account_id, acct_updates in by_account.items():
        ledger_path = ledger_data_dir / f"{account_id}.csv"
        if not ledger_path.exists():
            continue

        text = ledger_path.read_text(encoding="utf-8")
        groups = load_ledger_csv(text, default_currency="CAD")

        update_map = {u.transaction_id: u for u in acct_updates}
        for group in groups:
            txn_id = group.primary.transaction_id
            if txn_id in update_map:
                u = update_map[txn_id]
                group.primary.category = u.category
                group.primary.subcategory = u.subcategory

        ledger_path.write_text(dump_ledger_csv(groups), encoding="utf-8")


class CategorizationPersistenceService:
    """
    Service that orchestrates the emit-update-rebuild pattern for categorizations.

    This is the functional core - no I/O or UI dependencies beyond the injected
    storage objects.

    Responsibilities:
    - Emit TransactionCategorized events for each update
    - Write updated category values back to per-account CSV ledgers
    - Rebuild projections incrementally after all changes
    """

    def __init__(
        self,
        event_store: EventStore,
        projection_builder: ProjectionBuilder,
        ledger_data_dir: Path,
    ) -> None:
        self._event_store = event_store
        self._projection_builder = projection_builder
        self._ledger_data_dir = ledger_data_dir

    def persist_categorizations(
        self, updates: list[CategorizationUpdate]
    ) -> CategorizationPersistenceResult:
        """Emit events, update CSVs, and rebuild projections for a list of updates.

        Args:
            updates: List of categorization changes to apply.

        Returns:
            Result with counts of what was changed.
        """
        # 1. Emit events for all updates
        for update in updates:
            event = TransactionCategorized(
                transaction_id=update.transaction_id,
                category=update.category,
                subcategory=update.subcategory,
                source=update.source,
                confidence=update.confidence,
                event_timestamp=datetime.now(),
            )
            self._event_store.append_event(event)

        # 2. Group updates by account and write CSVs
        by_account: dict[str, list[CategorizationUpdate]] = {}
        for update in updates:
            by_account.setdefault(update.account_id, []).append(update)

        accounts_written: list[str] = []
        for account_id, acct_updates in by_account.items():
            ledger_path = self._ledger_data_dir / f"{account_id}.csv"
            if not ledger_path.exists():
                continue

            text = ledger_path.read_text(encoding="utf-8")
            groups = load_ledger_csv(text, default_currency="CAD")

            update_map = {u.transaction_id: u for u in acct_updates}
            for group in groups:
                txn_id = group.primary.transaction_id
                if txn_id in update_map:
                    u = update_map[txn_id]
                    group.primary.category = u.category
                    group.primary.subcategory = u.subcategory

            ledger_path.write_text(dump_ledger_csv(groups), encoding="utf-8")
            accounts_written.append(account_id)

        # 3. Rebuild projections
        self._projection_builder.rebuild_incremental(self._event_store)

        return CategorizationPersistenceResult(
            transactions_updated=len(updates),
            events_emitted=len(updates),
            accounts_written=accounts_written,
        )

    def persist_category_rename(
        self,
        matches: list[tuple[str, TransactionGroup]],
        to_category: str,
        to_subcategory: str | None,
    ) -> CategorizationPersistenceResult:
        """Rename categories across matched transactions.

        Applies the rename in-place to matched groups, writes back to per-account
        CSV ledgers, emits events, and rebuilds projections.

        Args:
            matches: List of (account_id, TransactionGroup) pairs to rename.
            to_category: The new category name.
            to_subcategory: The new subcategory name, or None to preserve existing.

        Returns:
            Result with counts of what was changed.
        """
        # Group by account
        by_account: dict[str, list[TransactionGroup]] = {}
        for account_id, group in matches:
            by_account.setdefault(account_id, []).append(group)

        # 1. Update CSVs
        accounts_written: list[str] = []
        for account_id, matched_groups in by_account.items():
            ledger_path = self._ledger_data_dir / f"{account_id}.csv"
            if not ledger_path.exists():
                continue

            text = ledger_path.read_text(encoding="utf-8")
            all_groups = load_ledger_csv(text, default_currency="CAD")

            matched_ids = {g.primary.transaction_id for g in matched_groups}
            for group in all_groups:
                if group.primary.transaction_id in matched_ids:
                    group.primary.category = to_category
                    if to_subcategory is not None:
                        group.primary.subcategory = to_subcategory

            ledger_path.write_text(dump_ledger_csv(all_groups), encoding="utf-8")
            accounts_written.append(account_id)

        # 2. Emit events for all matched groups
        for _account_id, group in matches:
            event = TransactionCategorized(
                transaction_id=group.primary.transaction_id,
                category=to_category,
                subcategory=to_subcategory,
                source="user",
                event_timestamp=datetime.now(),
            )
            self._event_store.append_event(event)

        # 3. Rebuild projections
        self._projection_builder.rebuild_incremental(self._event_store)

        return CategorizationPersistenceResult(
            transactions_updated=len(matches),
            events_emitted=len(matches),
            accounts_written=accounts_written,
        )

    def persist_note_update(
        self,
        account_id: str,
        transaction_id: str,
        note: str | None,
    ) -> None:
        """Update the note on a single transaction and write back to its ledger CSV.

        Delegates to the standalone :func:`persist_note_update` function.
        """
        persist_note_update(
            account_id=account_id,
            transaction_id=transaction_id,
            note=note,
            ledger_data_dir=self._ledger_data_dir,
        )


def persist_note_update(
    account_id: str,
    transaction_id: str,
    note: str | None,
    ledger_data_dir: Path,
) -> None:
    """Update the note on a single transaction and write back to its ledger CSV.

    Args:
        account_id: Account ID that owns the transaction (used to locate the ledger file).
        transaction_id: The transaction whose note should be updated.
        note: New note text, or None to clear the note.
        ledger_data_dir: Directory containing per-account CSV ledger files.

    Raises:
        FileNotFoundError: If the ledger CSV for the account does not exist.
    """
    ledger_path = ledger_data_dir / f"{account_id}.csv"
    if not ledger_path.exists():
        raise FileNotFoundError(f"Ledger file not found: {ledger_path}")

    text = ledger_path.read_text(encoding="utf-8")
    groups = load_ledger_csv(text, default_currency="CAD")

    for group in groups:
        if group.primary.transaction_id == transaction_id:
            group.primary.notes = note if note else None
            break

    ledger_path.write_text(dump_ledger_csv(groups), encoding="utf-8")


__all__ = [
    "CategorizationUpdate",
    "CategorizationPersistenceResult",
    "CategorizationPersistenceService",
    "persist_note_update",
    "write_categorizations_to_csv",
]
