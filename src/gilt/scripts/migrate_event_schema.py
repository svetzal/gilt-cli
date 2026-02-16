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
import json
import sqlite3
from typing import cast

from gilt.model.events import DuplicateSuggested
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def migrate_events(dry_run: bool = True):
    """Backfill pair data in DuplicateSuggested events.

    Args:
        dry_run: If True, show what would be changed without modifying database
    """
    workspace = Workspace.resolve()
    event_store = EventStore(str(workspace.event_store_path))
    projection_builder = ProjectionBuilder(workspace.projections_path)

    # Get all DuplicateSuggested events
    suggestions = event_store.get_events_by_type('DuplicateSuggested')

    print(f"Found {len(suggestions)} DuplicateSuggested events")

    # Check how many already have pair data
    with_pair = sum(1 for s in suggestions if isinstance(s, DuplicateSuggested) and 'pair' in s.assessment)
    without_pair = len(suggestions) - with_pair

    print(f"  - {with_pair} already have 'pair' field")
    print(f"  - {without_pair} need migration")

    if without_pair == 0:
        print("\nNo migration needed - all events already have pair data!")
        return

    # Load all transactions from projection for lookup
    print("\nLoading transactions from projection database...")
    transactions = projection_builder.get_all_transactions(include_duplicates=True)
    txn_by_id = {txn['transaction_id']: txn for txn in transactions}
    print(f"Loaded {len(txn_by_id)} transactions")

    # Open direct SQLite connection for updates
    conn = sqlite3.connect(str(workspace.event_store_path))
    cursor = conn.cursor()

    # Migrate each event
    migrated_count = 0
    skipped_count = 0

    for event in suggestions:
        if not isinstance(event, DuplicateSuggested):
            continue

        # Skip if already has pair data
        if 'pair' in event.assessment:
            continue

        # Look up both transactions
        txn1_id = event.transaction_id_1
        txn2_id = event.transaction_id_2

        txn1 = txn_by_id.get(txn1_id)
        txn2 = txn_by_id.get(txn2_id)

        if not txn1 or not txn2:
            print(f"⚠️  Skipping event {event.event_id[:8]} - missing transaction(s)")
            skipped_count += 1
            continue

        # Build pair data
        pair_data = {
            'txn1_id': txn1_id,
            'txn1_date': txn1['transaction_date'],
            'txn1_description': txn1['canonical_description'],
            'txn1_amount': float(txn1['amount']),
            'txn1_account': txn1['account_id'],
            'txn1_source_file': txn1.get('source_file'),
            'txn2_id': txn2_id,
            'txn2_date': txn2['transaction_date'],
            'txn2_description': txn2['canonical_description'],
            'txn2_amount': float(txn2['amount']),
            'txn2_account': txn2['account_id'],
            'txn2_source_file': txn2.get('source_file'),
        }

        # Update assessment to include pair
        event.assessment['pair'] = pair_data

        if not dry_run:
            # Serialize updated event to JSON
            event_data = event.model_dump_json()

            # Update event in database
            cursor.execute(
                "UPDATE events SET event_data = ? WHERE event_id = ?",
                (event_data, event.event_id)
            )

        migrated_count += 1

        if migrated_count <= 3:
            print(f"✓ Migrating event {event.event_id[:8]}: {txn1_id[:8]}...{txn2_id[:8]}")

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
        '--write',
        action='store_true',
        help='Apply migration (default is dry-run preview)'
    )

    args = parser.parse_args()

    migrate_events(dry_run=not args.write)


if __name__ == '__main__':
    main()
