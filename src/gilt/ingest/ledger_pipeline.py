"""Ledger I/O for ingest: reads raw CSVs and merges with existing ledgers.

Imperative shell — reads from disk.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from gilt.ingest.column_mapping import _detect_columns, _detect_rbc_overrides, find_missing_columns
from gilt.ingest.normalization import _build_transaction_dataframe
from gilt.ingest.transaction_mapping import _groups_to_dataframe
from gilt.model.ledger_io import STANDARD_FIELDS
from gilt.model.ledger_repository import LEDGER_IO_ERRORS, LedgerRepository
from gilt.model.raw_csv import load_raw_csv


def load_file(
    input_path: Path, account_id: str, amount_sign: str = "expenses_negative"
) -> pd.DataFrame:
    """Load and parse a CSV file into a normalized DataFrame of transactions.

    - Reads only the specified CSV locally using pandas.
    - Performs best-effort column mapping for date/description/amount/currency.
    - Computes a stable transaction_id.
    - Returns a DataFrame with STANDARD_FIELDS.
    """
    df = load_raw_csv(input_path)
    cols = list(df.columns)

    column_map = _detect_columns(cols)
    overrides = _detect_rbc_overrides(df, cols)

    missing = find_missing_columns(column_map, overrides)
    if missing:
        raise ValueError(
            f"Missing required columns in {input_path.name}: {', '.join(missing)}"
        )

    out = _build_transaction_dataframe(
        df, column_map, overrides, account_id, amount_sign, input_path
    )

    return (
        out[STANDARD_FIELDS]
        .sort_values(by=["date", "amount", "description"])
        .reset_index(drop=True)
    )


def _merge_with_existing_ledger(
    new_df: pd.DataFrame,
    ledger_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the existing ledger at ledger_path and merge new_df into it.

    Deduplicates by transaction_id: rows in new_df whose transaction_id already
    exists in the ledger are dropped before combining.

    Returns (combined_df, existing_df):
    - combined_df: merged result sorted by (date, amount, description)
    - existing_df: original ledger rows (needed by _emit_transaction_events)
    """
    try:
        existing_groups = LedgerRepository(ledger_path.parent).load(ledger_path.stem)
        existing = _groups_to_dataframe(existing_groups)
    except LEDGER_IO_ERRORS:
        existing = pd.DataFrame(columns=STANDARD_FIELDS)

    if len(existing) == 0:
        combined = new_df.copy()
    else:
        existing_ids = set(existing["transaction_id"].astype(str))
        new_filtered = new_df[~new_df["transaction_id"].astype(str).isin(existing_ids)]
        combined = pd.concat([existing, new_filtered], ignore_index=True)

    combined = (
        combined[STANDARD_FIELDS]
        .sort_values(by=["date", "amount", "description"])
        .reset_index(drop=True)
    )
    return combined, existing
