"""
Event-application functions for transaction projections.

Module-level functions that apply domain events to the projection SQLite database.
Each function takes an open connection and an event; no instance state is required.
"""

from __future__ import annotations

import json
import sqlite3

from gilt.model.events import (
    DuplicateConfirmed,
    DuplicateRejected,
    Event,
    TransactionCategorized,
    TransactionDescriptionObserved,
    TransactionEnriched,
    TransactionImported,
)
from gilt.storage.duplicate_normalization import find_root_primary


def apply_events(
    conn: sqlite3.Connection, events: list[Event], start_sequence: int
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
            _apply_transaction_imported(conn, event)
        elif isinstance(event, TransactionDescriptionObserved):
            _apply_description_observed(conn, event)
        elif isinstance(event, TransactionCategorized):
            _apply_transaction_categorized(conn, event)
        elif isinstance(event, TransactionEnriched):
            _apply_transaction_enriched(conn, event)
        elif isinstance(event, DuplicateConfirmed):
            _apply_duplicate_confirmed(conn, event)
        elif isinstance(event, DuplicateRejected):
            _apply_duplicate_rejected(conn, event)

        processed += 1

    if events:
        last_event_seq = start_sequence + processed
        conn.execute(
            """
            INSERT OR REPLACE INTO projection_metadata (key, value)
            VALUES ('last_sequence', ?)
            """,
            (str(last_event_seq),),
        )

    conn.commit()
    return processed


def _apply_transaction_imported(
    conn: sqlite3.Connection, event: TransactionImported
) -> None:
    cursor = conn.execute(
        "SELECT transaction_id FROM transaction_projections WHERE transaction_id = ?",
        (event.transaction_id,),
    )
    if cursor.fetchone():
        return

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
        ),
    )


def _link_duplicate_if_present(
    conn: sqlite3.Connection, event: TransactionDescriptionObserved
) -> None:
    original_id = event.original_transaction_id
    new_id = event.new_transaction_id

    if original_id == new_id:
        return

    cursor = conn.execute(
        "SELECT transaction_id FROM transaction_projections WHERE transaction_id = ?",
        (new_id,),
    )
    if cursor.fetchone():
        root_id, _ = _resolve_root_primary(conn, original_id)
        actual_primary = root_id if root_id else original_id

        conn.execute(
            """
            UPDATE transaction_projections
            SET is_duplicate = 1,
                primary_transaction_id = ?,
                last_event_id = ?
            WHERE transaction_id = ?
            """,
            (
                actual_primary,
                event.event_id,
                new_id,
            ),
        )


def _apply_description_observed(
    conn: sqlite3.Connection, event: TransactionDescriptionObserved
) -> None:
    cursor = conn.execute(
        """
        SELECT canonical_description, description_history
        FROM transaction_projections
        WHERE transaction_id = ?
        """,
        (event.original_transaction_id,),
    )
    row = cursor.fetchone()

    if not row:
        return

    canonical_desc, history_json = row
    history = json.loads(history_json) if history_json else []

    if event.new_description not in history:
        history.append(event.new_description)

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
        ),
    )

    _link_duplicate_if_present(conn, event)


def _apply_transaction_categorized(
    conn: sqlite3.Connection, event: TransactionCategorized
) -> None:
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
        ),
    )


def _apply_transaction_enriched(
    conn: sqlite3.Connection, event: TransactionEnriched
) -> None:
    conn.execute(
        """
        UPDATE transaction_projections
        SET vendor = ?,
            service = ?,
            invoice_number = ?,
            tax_amount = ?,
            tax_type = ?,
            enrichment_currency = ?,
            receipt_file = ?,
            enrichment_source = ?,
            source_email = ?,
            last_event_id = ?
        WHERE transaction_id = ?
        """,
        (
            event.vendor,
            event.service,
            event.invoice_number,
            float(event.tax_amount) if event.tax_amount is not None else None,
            event.tax_type,
            event.currency,
            event.receipt_file,
            event.enrichment_source,
            event.source_email,
            event.event_id,
            event.transaction_id,
        ),
    )


def _apply_duplicate_confirmed(
    conn: sqlite3.Connection, event: DuplicateConfirmed
) -> None:
    primary_id = event.primary_transaction_id
    duplicate_id = event.duplicate_transaction_id

    if primary_id == duplicate_id:
        return

    cursor = conn.execute(
        "SELECT is_duplicate, primary_transaction_id FROM transaction_projections "
        "WHERE transaction_id = ?",
        (primary_id,),
    )
    primary_row = cursor.fetchone()
    if primary_row and primary_row[0]:
        root_id, _ = _resolve_root_primary(conn, primary_id)
        if root_id:
            primary_id = root_id

    cursor = conn.execute(
        "SELECT primary_transaction_id FROM transaction_projections WHERE transaction_id = ?",
        (primary_id,),
    )
    primary_ptr_row = cursor.fetchone()
    if primary_ptr_row and primary_ptr_row[0] == duplicate_id:
        conn.execute(
            """
            UPDATE transaction_projections
            SET is_duplicate = 0,
                primary_transaction_id = NULL
            WHERE transaction_id = ?
            """,
            (primary_id,),
        )

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
            primary_id,
        ),
    )

    conn.execute(
        """
        UPDATE transaction_projections
        SET is_duplicate = 1,
            primary_transaction_id = ?,
            last_event_id = ?
        WHERE transaction_id = ?
        """,
        (
            primary_id,
            event.event_id,
            duplicate_id,
        ),
    )


def _apply_duplicate_rejected(
    conn: sqlite3.Connection, event: DuplicateRejected
) -> None:
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
        ),
    )


def _resolve_root_primary(
    conn: sqlite3.Connection, txn_id: str, max_hops: int = 8
) -> tuple[str | None, list[str]]:
    """Thin wrapper: resolves root via DB query, delegating logic to find_root_primary."""

    def _lookup(t_id: str) -> tuple[bool, str | None] | None:
        cursor = conn.execute(
            "SELECT is_duplicate, primary_transaction_id FROM transaction_projections "
            "WHERE transaction_id = ?",
            (t_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return bool(row[0]), row[1]

    return find_root_primary(_lookup, txn_id, max_hops)
