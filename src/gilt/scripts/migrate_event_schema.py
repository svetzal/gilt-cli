#!/usr/bin/env python3
"""
Migrate DuplicateSuggested events to include complete TransactionPair data.

This script backfills the 'pair' field in existing DuplicateSuggested events
by looking up transaction details from the projection database. This enables
ML training on historical user feedback.

Usage:
    python src/gilt/scripts/migrate_event_schema.py [--dry-run]
"""

import argparse
import sqlite3

from gilt.model.events import DuplicateSuggested
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def _load_workspace_resources(workspace) -> tuple:
    """Load event store, suggestions, and transaction lookup from workspace.

    Args:
        workspace: Resolved Workspace instance

    Returns:
        Tuple of (event_store, suggestions, txn_by_id)
    """
    event_store = EventStore(str(workspace.event_store_path))
    projection_builder = ProjectionBuilder(workspace.projections_path)

    suggestions = event_store.get_events_by_type("DuplicateSuggested")

    transactions = projection_builder.get_all_transactions(include_duplicates=True)
    txn_by_id = {txn["transaction_id"]: txn for txn in transactions}

    return event_store, suggestions, txn_by_id


def _build_pair_data(txn1: dict, txn2: dict, txn1_id: str, txn2_id: str) -> dict:
    """Build the pair_data dict from two transaction dicts.

    Args:
        txn1: First transaction dict from projection
        txn2: Second transaction dict from projection
        txn1_id: ID of the first transaction
        txn2_id: ID of the second transaction

    Returns:
        pair_data dict ready to embed in event assessment
    """
    return {
        "txn1_id": txn1_id,
        "txn1_date": txn1["transaction_date"],
        "txn1_description": txn1["canonical_description"],
        "txn1_amount": float(txn1["amount"]),
        "txn1_account": txn1["account_id"],
        "txn1_source_file": txn1.get("source_file"),
        "txn2_id": txn2_id,
        "txn2_date": txn2["transaction_date"],
        "txn2_description": txn2["canonical_description"],
        "txn2_amount": float(txn2["amount"]),
        "txn2_account": txn2["account_id"],
        "txn2_source_file": txn2.get("source_file"),
    }


def _migrate_single_event(
    cursor, event, txn_by_id: dict, dry_run: bool, migrated_count: int
) -> tuple[int, int]:
    """Migrate one DuplicateSuggested event by backfilling its pair data.

    Args:
        cursor: SQLite cursor for writing updates
        event: DuplicateSuggested event to process
        txn_by_id: Mapping of transaction_id to transaction dict
        dry_run: If True, skip database writes
        migrated_count: Running count of already-migrated events (used for log throttle)

    Returns:
        Tuple of (new_migrated, new_skipped) increment counts (each 0 or 1)
    """
    if not isinstance(event, DuplicateSuggested):
        return 0, 0

    if "pair" in event.assessment:
        return 0, 0

    txn1_id = event.transaction_id_1
    txn2_id = event.transaction_id_2

    txn1 = txn_by_id.get(txn1_id)
    txn2 = txn_by_id.get(txn2_id)

    if not txn1 or not txn2:
        print(f"⚠️  Skipping event {event.event_id[:8]} - missing transaction(s)")
        return 0, 1

    event.assessment["pair"] = _build_pair_data(txn1, txn2, txn1_id, txn2_id)

    if not dry_run:
        event_data = event.model_dump_json()
        cursor.execute(
            "UPDATE events SET event_data = ? WHERE event_id = ?", (event_data, event.event_id)
        )

    if migrated_count < 3:
        print(f"✓ Migrating event {event.event_id[:8]}: {txn1_id[:8]}...{txn2_id[:8]}")

    return 1, 0


def migrate_events(dry_run: bool = True):
    """Backfill pair data in DuplicateSuggested events.

    Args:
        dry_run: If True, show what would be changed without modifying database
    """
    workspace = Workspace.resolve()

    print("\nLoading transactions from projection database...")
    event_store, suggestions, txn_by_id = _load_workspace_resources(workspace)
    print(f"Loaded {len(txn_by_id)} transactions")

    print(f"Found {len(suggestions)} DuplicateSuggested events")

    with_pair = sum(
        1 for s in suggestions if isinstance(s, DuplicateSuggested) and "pair" in s.assessment
    )
    without_pair = len(suggestions) - with_pair

    print(f"  - {with_pair} already have 'pair' field")
    print(f"  - {without_pair} need migration")

    if without_pair == 0:
        print("\nNo migration needed - all events already have pair data!")
        return

    conn = sqlite3.connect(str(workspace.event_store_path))
    cursor = conn.cursor()

    migrated_count = 0
    skipped_count = 0

    for event in suggestions:
        new_migrated, new_skipped = _migrate_single_event(
            cursor, event, txn_by_id, dry_run, migrated_count
        )
        migrated_count += new_migrated
        skipped_count += new_skipped

    if not dry_run:
        conn.commit()

    conn.close()

    print(f"\n{'Would migrate' if dry_run else 'Migrated'} {migrated_count} events")
    if skipped_count > 0:
        print(f"Skipped {skipped_count} events (missing transactions)")

    if dry_run:
        print("\n⚠️  DRY RUN - No changes made. Use --write to apply migration.")
    else:
        print("\n✓ Migration complete!")
        print(f"Updated {migrated_count} DuplicateSuggested events with pair data")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate DuplicateSuggested events to include TransactionPair data"
    )
    parser.add_argument(
        "--write", action="store_true", help="Apply migration (default is dry-run preview)"
    )

    args = parser.parse_args()

    migrate_events(dry_run=not args.write)


if __name__ == "__main__":
    main()
