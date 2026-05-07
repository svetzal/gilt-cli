from __future__ import annotations

"""
Gilt ingest module

Refactored from gilt.cli.ingest_normalize into a reusable module.
Provides local-only ingestion utilities to normalize bank CSV exports under
ingest/ into standardized per-account ledgers under data/accounts/.

Key functions:
- load_accounts_config(path): load config/accounts.yml into Account models
- infer_account_for_file(accounts, file_path): map an ingest file to account_id
- plan_normalization(inputs, output_dir, accounts): preview mapping
- normalize_file(input_path, account_id, output_dir): write/update ledger CSV

No network I/O. All operations are local, privacy-first.
"""

import fnmatch
import hashlib
import logging
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from pydantic import ValidationError

try:
    import yaml  # optional; used for local config parsing
except ImportError:  # pragma: no cover
    yaml = None

from gilt.model.account import Account
from gilt.model.ledger_io import STANDARD_FIELDS
from gilt.model.ledger_repository import LEDGER_IO_ERRORS
from gilt.model.raw_csv import load_raw_csv

if TYPE_CHECKING:
    from gilt.storage.event_store import EventStore

logger = logging.getLogger(__name__)


def load_accounts_config(path: Path) -> list[Account]:
    """Load accounts config from YAML locally (safe loader).

    Returns a list of Account models. If YAML is unavailable or file missing,
    returns an empty list. No network access is performed.
    """
    accounts: list[Account] = []
    try:
        if yaml is None:
            # Proceed without config
            return accounts
        if not path.exists():
            return accounts
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for item in data.get("accounts") or []:
            try:
                accounts.append(Account.model_validate(item))
            except ValidationError:  # pragma: no cover
                # Skip invalid entries; keep local processing resilient
                continue
    except (yaml.YAMLError, OSError):  # pragma: no cover
        # Swallow and return best-effort empty config
        logger.warning("Failed to load accounts config from %s", path, exc_info=True)
        return accounts
    return accounts


def infer_account_for_file(accounts: Sequence[Account], file_path: Path) -> Account | None:
    """Infer which configured account a file likely belongs to.

    Priority:
    1) If accounts are provided, match filename against source_patterns.
    2) If no accounts are available, apply simple filename heuristics as a fallback.
    """
    fname = file_path.name
    # 1) Config-driven matching (match by filename; patterns are name-only, ingest/ is fixed)
    for acct in accounts:
        for pattern in acct.source_patterns or []:
            if fnmatch.fnmatch(fname, pattern) or fnmatch.fnmatch(str(file_path), pattern):
                return acct

    # 2) Heuristic fallback (no config loaded)
    lower = fname.lower()
    if "rbc" in lower and "chequ" in lower:
        return Account(account_id="RBC_CHQ")
    if "scotia" in lower and "current" in lower:
        return Account(account_id="SCOTIA_CURR")
    if "scotia" in lower and "line" in lower:
        return Account(account_id="SCOTIA_LOC")

    return None


# Frozen transaction_id hash spec: do not change without a migration plan.
HASH_ALGO_SPEC = (
    "v1: sha256 of 'account_id|date|amount|description' using values exactly as"
    " written to output columns (date in YYYY-MM-DD; amount via Python str();"
    " description as-is)."
)


def compute_transaction_id_fields(account_id: str, date: str, amount, description: str) -> str:
    base = f"{account_id}|{date}|{amount}|{description}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _first_match(name_candidates: list[str], available: list[str]) -> str | None:
    """Return the first candidate found (case-insensitive) in available column names."""
    lower_map = {c.lower(): c for c in available}
    for cand in name_candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def plan_normalization(
    inputs: Sequence[Path], output_dir: Path, accounts: Sequence[Account]
) -> list[tuple[Path, str | None]]:
    """Plan which files would be normalized and the target account_id.

    Returns a list of (input_path, account_id_or_none) without performing IO.
    """
    plan: list[tuple[Path, str | None]] = []
    for p in inputs:
        acct = infer_account_for_file(accounts, p)
        plan.append((p, acct.account_id if acct else None))
    return plan


def _detect_columns(cols: list[str]) -> dict[str, str | None]:
    """Map logical column roles to actual column names found in a CSV header.

    Returns a dict with keys: "date", "desc1", "desc2", "amount", "usd", "currency".
    Each value is the matched column name or None if not found.
    Pure function — no side effects.
    """
    return {
        "date": _first_match(["Date", "Transaction Date", "Posted Date", "date"], cols),
        "desc1": _first_match(
            [
                "Description 1",
                "Description",
                "description",
                "Memo",
                "Details",
                "Memo/Description",
                "Payee",
                "Name",
                "Merchant",
                "Transaction Description",
                "Payee/Description",
            ],
            cols,
        ),
        "desc2": _first_match(["Description 2"], cols),
        "amount": _first_match(["CAD$", "Amount", "amount"], cols),
        "usd": _first_match(["USD$"], cols),
        "currency": _first_match(["Currency", "currency"], cols),
    }


_RBC_REQUIRED_COLS = [
    "Account Type",
    "Account Number",
    "Transaction Date",
    "Cheque Number",
    "Description 1",
    "Description 2",
    "CAD$",
    "USD$",
]


def _detect_rbc_overrides(df: pd.DataFrame, cols: list[str]) -> dict[str, pd.Series]:
    """Detect and correct the RBC CSV column-shift quirk.

    Some RBC exports have a shifted header where "Transaction Date" is empty and
    actual dates appear in "Account Number". When detected, returns a dict with
    corrected series for: "date_series", "desc1_series", "desc2_series", "amount_series".
    Returns an empty dict if the DataFrame does not exhibit the RBC quirk.
    Pure function over the DataFrame.
    """
    rbc_like = all(col in cols for col in _RBC_REQUIRED_COLS)
    if not rbc_like:
        return {}

    txn_date_empty = (df["Transaction Date"].astype(str).str.strip() == "").all()
    acc_looks_like_date = (
        df["Account Number"]
        .astype(str)
        .str.strip()
        .str.match(r"^\d{1,2}/\d{1,2}/\d{4}$")
        .mean()
        > 0.5
    )
    if txn_date_empty and acc_looks_like_date:
        return {
            "date_series": df["Account Number"].astype(str).str.strip(),
            "desc1_series": df["Cheque Number"].astype(str),
            "desc2_series": df["Description 1"].astype(str),
            "amount_series": df["Description 2"].astype(str),
        }
    return {}


def _build_transaction_dataframe(
    df: pd.DataFrame,
    column_map: dict[str, str | None],
    overrides: dict[str, pd.Series],
    account_id: str,
    amount_sign: str,
    input_path: Path,
) -> pd.DataFrame:
    """Build the normalized transaction DataFrame from a raw CSV DataFrame.

    Handles date parsing, description combination, amount extraction, currency
    assignment, boilerplate fields, and transaction ID computation.
    Returns a DataFrame without final reordering or sorting (caller's responsibility).
    Pure function over its inputs.
    """
    out = pd.DataFrame()

    # Date: strip and parse; keep YYYY-MM-DD; coerce invalid to NaN
    date_series = (
        overrides["date_series"]
        if "date_series" in overrides
        else df[column_map["date"]].astype(str).str.strip()
    )
    out["date"] = pd.to_datetime(date_series, errors="coerce", dayfirst=False).dt.strftime(
        "%Y-%m-%d"
    )

    # Description: combine desc1 and desc2 when present; join with ' - ' and strip
    d1 = (
        overrides["desc1_series"]
        if "desc1_series" in overrides
        else (
            df[column_map["desc1"]].astype(str)
            if column_map["desc1"]
            else pd.Series("", index=df.index)
        )
    )
    d2 = (
        overrides["desc2_series"]
        if "desc2_series" in overrides
        else (
            df[column_map["desc2"]].astype(str)
            if column_map["desc2"]
            else pd.Series("", index=df.index)
        )
    )
    d1 = d1.fillna("").str.strip()
    d2 = d2.fillna("").str.strip()
    combined_desc = d1.where(d2.eq(""), d1.str.cat(d2, sep=" - "))
    out["description"] = combined_desc.fillna("").astype(str).str.strip()

    # Amount handling
    if "amount_series" in overrides:
        amt_src = overrides["amount_series"]
    elif column_map["amount"] is not None:
        amt_src = df[column_map["amount"]]
    elif column_map["usd"] is not None:
        amt_src = df[column_map["usd"]]
    else:
        amt_src = pd.Series("", index=df.index)
    amt_str = amt_src.astype(str).fillna("").str.strip()
    amt_str = amt_str.str.replace(r"[,$]", "", regex=True)
    amt_str = amt_str.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    out["amount"] = pd.to_numeric(amt_str, errors="coerce")

    # Apply amount sign convention: negate if bank reports expenses as positive
    if amount_sign == "expenses_positive":
        out["amount"] = -out["amount"]

    if column_map["currency"]:
        out["currency"] = df[column_map["currency"]].astype(str).replace("", "CAD")
    else:
        out["currency"] = "CAD"

    out["account_id"] = account_id
    out["counterparty"] = out["description"]
    out["category"] = None
    out["subcategory"] = None
    out["notes"] = None
    out["source_file"] = input_path.name

    # Compute transaction_id hash (frozen spec)
    out["transaction_id"] = out.apply(
        lambda row: compute_transaction_id_fields(
            row["account_id"], row["date"], row["amount"], row["description"]
        ),
        axis=1,
    )

    return out


def parse_file(
    input_path: Path, account_id: str, amount_sign: str = "expenses_negative"
) -> pd.DataFrame:
    """Parse a CSV file into a normalized DataFrame of transactions.

    - Reads only the specified CSV locally using pandas.
    - Performs best-effort column mapping for date/description/amount/currency.
    - Computes a stable transaction_id.
    - Returns a DataFrame with STANDARD_FIELDS.
    """
    df = load_raw_csv(input_path)
    cols = list(df.columns)

    column_map = _detect_columns(cols)
    overrides = _detect_rbc_overrides(df, cols)

    # Validate presence of core columns
    missing = []
    if column_map["date"] is None and "date_series" not in overrides:
        missing.append("date")
    if (
        column_map["desc1"] is None
        and column_map["desc2"] is None
        and "desc1_series" not in overrides
        and "desc2_series" not in overrides
    ):
        missing.append("description")
    if column_map["amount"] is None and column_map["usd"] is None and "amount_series" not in overrides:
        missing.append("amount")
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
    from gilt.model.events import TransactionDescriptionObserved, TransactionImported

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

        # Check for description changes: same date/amount/account but different description
        key = (str(row["date"]), str(row["amount"]), str(row["account_id"]))
        if key in existing_by_key:
            original_id, original_desc = existing_by_key[key]
            current_desc = str(row["description"])

            if original_id != txn_id and original_desc != current_desc:
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

        # Only emit TransactionImported events for new transactions
        if txn_id not in existing_ids:
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
        existing = pd.read_csv(ledger_path) if ledger_path.exists() else pd.DataFrame(columns=new_df.columns)
    except LEDGER_IO_ERRORS:
        existing = pd.DataFrame(columns=new_df.columns)

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
    out = parse_file(input_path, account_id, amount_sign=amount_sign)

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

    combined.to_csv(ledger_path, index=False)
    return ledger_path


__all__ = [
    "STANDARD_FIELDS",
    "load_accounts_config",
    "infer_account_for_file",
    "plan_normalization",
    "normalize_file",
    "compute_transaction_id_fields",
    "HASH_ALGO_SPEC",
]
