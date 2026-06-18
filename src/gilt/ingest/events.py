"""Event emission for ingest: fires domain events to the event store.

Imperative shell — writes events as a side effect.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from gilt.storage.event_store import EventStore

logger = logging.getLogger(__name__)


def _emit_description_observed_event(
    event_store: EventStore,
    row: pd.Series,
    key: tuple[str, str, str],
    existing_by_key: dict[tuple[str, str, str], tuple[str, str]],
    txn_id: str,
    input_path: Path,
    account_id: str,
) -> None:
    """Emit a TransactionDescriptionObserved event when a description change is detected.

    Fires when the same date/amount/account_id triple exists in the ledger but
    the description (and therefore transaction_id) has changed.
    """
    from gilt.model.events import TransactionDescriptionObserved

    if key not in existing_by_key:
        return

    original_id, original_desc = existing_by_key[key]
    current_desc = str(row["description"])

    if original_id == txn_id or original_desc == current_desc:
        return

    try:
        event = TransactionDescriptionObserved(
            original_transaction_id=original_id,
            new_transaction_id=txn_id,
            transaction_date=str(row["date"]),
            original_description=original_desc,
            new_description=current_desc,
            source_file=input_path.name,
            source_account=account_id,
            amount=Decimal(str(row["amount"])),
        )
        event_store.append_event(event)
    except (ValueError, TypeError) as e:
        logger.warning(
            "Skipped TransactionDescriptionObserved for txn %s (%r): %s",
            txn_id,
            original_desc,
            e,
        )


def _emit_transaction_imported_event(
    event_store: EventStore,
    row: pd.Series,
    txn_id: str,
    existing_ids: set[str],
    input_path: Path,
    account_id: str,
) -> None:
    """Emit a TransactionImported event for a transaction not yet in the ledger."""
    from gilt.model.events import TransactionImported

    if txn_id in existing_ids:
        return

    try:
        event = TransactionImported(
            transaction_date=str(row["date"]),
            transaction_id=txn_id,
            source_file=input_path.name,
            source_account=account_id,
            raw_description=str(row["description"]),
            amount=Decimal(str(row["amount"])),
            currency=str(row["currency"]),
            raw_data={},
        )
        event_store.append_event(event)
    except (ValueError, TypeError) as e:
        logger.warning(
            "Skipped TransactionImported for txn %s (amount=%s): %s",
            txn_id,
            row["amount"],
            e,
        )


def _emit_transaction_events(
    out: pd.DataFrame,
    existing: pd.DataFrame,
    event_store: EventStore,
    input_path: Path,
    account_id: str,
) -> None:
    """Emit TransactionImported and TransactionDescriptionObserved events for new/changed rows.

    Compares `out` (newly parsed transactions) against `existing` (current ledger) and
    emits events to `event_store` for each new transaction and each description change.
    """
    existing_ids = set(existing["transaction_id"].astype(str)) if len(existing) > 0 else set()

    # Build index of existing transactions by (date, amount, account_id)
    existing_by_key: dict[tuple[str, str, str], tuple[str, str]] = {}
    if len(existing) > 0:
        for _, ex_row in existing.iterrows():
            key = (str(ex_row["date"]), str(ex_row["amount"]), str(ex_row["account_id"]))
            existing_by_key[key] = (str(ex_row["transaction_id"]), str(ex_row["description"]))

    for _, row in out.iterrows():
        txn_id = str(row["transaction_id"])

        # Skip rows with invalid data (NaN amounts, invalid dates)
        if pd.isna(row["amount"]) or pd.isna(row["date"]):
            continue

        key = (str(row["date"]), str(row["amount"]), str(row["account_id"]))
        _emit_description_observed_event(
            event_store, row, key, existing_by_key, txn_id, input_path, account_id
        )
        _emit_transaction_imported_event(
            event_store, row, txn_id, existing_ids, input_path, account_id
        )
