from __future__ import annotations

"""
Gilt ingest module

Refactored from gilt.cli.ingest_normalize into a reusable module.
Provides local-only ingestion utilities to normalize bank CSV exports under
ingest/ into standardized per-account ledgers under data/accounts/.

Key functions:
- load_accounts_config(path): load config/accounts.yml into Account models
- infer_account_for_file(accounts, file_path): map an ingest file to account_id
- build_normalization_plan(inputs, output_dir, accounts): preview mapping
- normalize_file(input_path, account_id, output_dir): write/update ledger CSV
- load_file(input_path, account_id): parse a bank CSV into normalized DataFrame

No network I/O. All operations are local, privacy-first.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from gilt.ingest.account_matching import build_normalization_plan, infer_account_for_file
from gilt.ingest.column_mapping import (
    _detect_columns as _detect_columns,
)
from gilt.ingest.column_mapping import (
    _detect_rbc_overrides as _detect_rbc_overrides,
)
from gilt.ingest.column_mapping import (
    find_missing_columns,
)
from gilt.ingest.config_loader import load_accounts_config
from gilt.ingest.events import _emit_transaction_events
from gilt.ingest.ledger_pipeline import _merge_with_existing_ledger, load_file
from gilt.ingest.normalization import HASH_ALGO_SPEC, build_transaction_id
from gilt.ingest.transaction_mapping import (
    _dataframe_to_groups,
    build_groups_from_dataframe,
    build_transactions_from_dataframe,
)
from gilt.model.ledger_io import STANDARD_FIELDS
from gilt.model.ledger_repository import LedgerRepository

if TYPE_CHECKING:
    from gilt.storage.event_store import EventStore


def normalize_file(
    input_path: Path,
    account_id: str,
    output_dir: Path,
    event_store: EventStore | None = None,
    exclude_ids: list[str] | None = None,
    categorization_map: dict[str, str] | None = None,
    amount_sign: str = "expenses_negative",
) -> Path:
    """Normalize a single CSV into the standardized schema and write to output_dir as a ledger.

    - Reads only the specified CSV locally using pandas.
    - Performs best-effort column mapping for date/description/amount/currency.
    - Computes a stable transaction_id.
    - Writes/updates per-account ledger CSV under output_dir: '{account_id}.csv'.
    - If event_store is provided, emits TransactionImported events (dual-write pattern).
    - Returns the output file path (ledger path).
    """
    out = load_file(input_path, account_id, amount_sign=amount_sign)

    if exclude_ids:
        out = out[~out["transaction_id"].isin(exclude_ids)]

    if categorization_map:
        for txn_id, category in categorization_map.items():
            out.loc[out["transaction_id"] == txn_id, "category"] = category

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / f"{account_id}.csv"

    combined, existing = _merge_with_existing_ledger(out, ledger_path)

    if event_store is not None:
        _emit_transaction_events(out, existing, event_store, input_path, account_id)

    LedgerRepository(output_dir).save(account_id, _dataframe_to_groups(combined))
    return ledger_path


__all__ = [
    "STANDARD_FIELDS",
    "load_accounts_config",
    "load_file",
    "infer_account_for_file",
    "build_normalization_plan",
    "find_missing_columns",
    "normalize_file",
    "build_transaction_id",
    "build_groups_from_dataframe",
    "build_transactions_from_dataframe",
    "HASH_ALGO_SPEC",
]
