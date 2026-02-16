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

from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Dict
import fnmatch
import hashlib

import pandas as pd

try:
    import yaml  # optional; used for local config parsing
except Exception:  # pragma: no cover
    yaml = None

from gilt.model.account import Account

# Public constant: standardized processed schema
STANDARD_FIELDS = [
    "transaction_id",
    "date",
    "description",
    "amount",
    "currency",
    "account_id",
    "counterparty",
    "category",
    "subcategory",
    "notes",
    "source_file",
]


def load_accounts_config(path: Path) -> List[Account]:
    """Load accounts config from YAML locally (safe loader).

    Returns a list of Account models. If YAML is unavailable or file missing,
    returns an empty list. No network access is performed.
    """
    accounts: List[Account] = []
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
            except Exception:  # pragma: no cover
                # Skip invalid entries; keep local processing resilient
                continue
    except Exception:  # pragma: no cover
        # Swallow and return best-effort empty config
        return accounts
    return accounts


def infer_account_for_file(accounts: Sequence[Account], file_path: Path) -> Optional[Account]:
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


def _first_match(name_candidates: List[str], available: List[str]) -> Optional[str]:
    """Return the first candidate found (case-insensitive) in available column names."""
    lower_map = {c.lower(): c for c in available}
    for cand in name_candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def plan_normalization(
    inputs: Sequence[Path], output_dir: Path, accounts: Sequence[Account]
) -> List[Tuple[Path, Optional[str]]]:
    """Plan which files would be normalized and the target account_id.

    Returns a list of (input_path, account_id_or_none) without performing IO.
    """
    plan: List[Tuple[Path, Optional[str]]] = []
    for p in inputs:
        acct = infer_account_for_file(accounts, p)
        plan.append((p, acct.account_id if acct else None))
    return plan


def parse_file(input_path: Path, account_id: str) -> pd.DataFrame:
    """Parse a CSV file into a normalized DataFrame of transactions.

    - Reads only the specified CSV locally using pandas.
    - Performs best-effort column mapping for date/description/amount/currency.
    - Computes a stable transaction_id.
    - Returns a DataFrame with STANDARD_FIELDS.
    """
    # Read CSV with robust defaults for bank exports (handle BOM and text preservation)
    df = pd.read_csv(input_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)

    # Prepare column mapping heuristics (extend as needed)
    cols = list(df.columns)
    date_col = _first_match(["Date", "Transaction Date", "Posted Date", "date"], cols)

    # Prefer combining Description 1 and Description 2 when both exist
    desc1_col = _first_match(
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
    )
    desc2_col = _first_match(["Description 2"], cols)

    # Amount column candidates (prefer CAD$, else Amount)
    amt_col = _first_match(["CAD$", "Amount", "amount"], cols)
    # Secondary amount in USD if CAD missing (rare for CAD accounts but safer)
    usd_col = _first_match(["USD$"], cols)

    cur_col = _first_match(["Currency", "currency"], cols)

    # RBC CSV quirk correction
    rbc_like = all(
        col in cols
        for col in [
            "Account Type",
            "Account Number",
            "Transaction Date",
            "Cheque Number",
            "Description 1",
            "Description 2",
            "CAD$",
            "USD$",
        ]
    )
    override = {}
    if rbc_like:
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
            override["date_series"] = df["Account Number"].astype(str).str.strip()
            override["desc1_series"] = df["Cheque Number"].astype(str)
            override["desc2_series"] = df["Description 1"].astype(str)
            override["amount_series"] = df["Description 2"].astype(str)

    # Validate presence of core columns
    missing = []
    if (date_col is None) and ("date_series" not in override):
        missing.append("date")
    if (
        (desc1_col is None)
        and (desc2_col is None)
        and ("desc1_series" not in override)
        and ("desc2_series" not in override)
    ):
        missing.append("description")
    if (amt_col is None) and (usd_col is None) and ("amount_series" not in override):
        missing.append("amount")
    if missing:
        raise ValueError(f"Missing required columns in {input_path.name}: {', '.join(missing)}")

    out = pd.DataFrame()

    # Date: strip and parse; keep YYYY-MM-DD; coerce invalid to NaN
    if "date_series" in override:
        date_series = override["date_series"]
    else:
        date_series = df[date_col].astype(str).str.strip()
    out["date"] = pd.to_datetime(date_series, errors="coerce", dayfirst=False).dt.strftime(
        "%Y-%m-%d"
    )

    # Description: combine 1 and 2 when present; join with ' - ' and strip
    d1 = (
        override.get("desc1_series")
        if "desc1_series" in override
        else (df[desc1_col].astype(str) if desc1_col else pd.Series("", index=df.index))
    )
    d2 = (
        override.get("desc2_series")
        if "desc2_series" in override
        else (df[desc2_col].astype(str) if desc2_col else pd.Series("", index=df.index))
    )
    d1 = d1.fillna("").str.strip()
    d2 = d2.fillna("").str.strip()
    combined_desc = d1
    combined_desc = combined_desc.where(d2.eq(""), combined_desc.str.cat(d2, sep=" - "))
    out["description"] = combined_desc.fillna("").astype(str).str.strip()

    # Amount handling
    if "amount_series" in override:
        amt_src = override["amount_series"]
    else:
        if amt_col is not None:
            amt_src = df[amt_col]
        elif usd_col is not None:
            amt_src = df[usd_col]
        else:
            amt_src = pd.Series("", index=df.index)
    amt_str = amt_src.astype(str).fillna("").str.strip()
    amt_str = amt_str.str.replace(r"[,$]", "", regex=True)
    amt_str = amt_str.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    out["amount"] = pd.to_numeric(amt_str, errors="coerce")

    if cur_col:
        out["currency"] = df[cur_col].astype(str).replace("", "CAD")
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

    # Reorder columns and sort for deterministic output
    out = (
        out[STANDARD_FIELDS]
        .sort_values(by=["date", "amount", "description"])
        .reset_index(drop=True)
    )
    return out


def normalize_file(
    input_path: Path,
    account_id: str,
    output_dir: Path,
    event_store: Optional["EventStore"] = None,
    exclude_ids: Optional[List[str]] = None,
    categorization_map: Optional[Dict[str, str]] = None,
) -> Path:
    """Normalize a single CSV into the standardized schema and write to output_dir as a ledger.

    - Reads only the specified CSV locally using pandas.
    - Performs best-effort column mapping for date/description/amount/currency.
    - Computes a stable transaction_id.
    - Writes/updates per-account ledger CSV under output_dir: '{account_id}.csv'.
    - If event_store is provided, emits TransactionImported events (dual-write pattern).
    - Returns the output file path (ledger path).
    """
    from gilt.model.events import TransactionImported

    # Parse file into normalized DataFrame
    out = parse_file(input_path, account_id)

    # Filter out excluded IDs (e.g. confirmed duplicates)
    if exclude_ids:
        out = out[~out["transaction_id"].isin(exclude_ids)]

    # Apply categorization
    if categorization_map:
        for txn_id, category in categorization_map.items():
            out.loc[out["transaction_id"] == txn_id, "category"] = category

    # Need original DF for raw data in events
    df = pd.read_csv(input_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write/update per-account ledger file
    ledger_path = output_dir / f"{account_id}.csv"
    try:
        if ledger_path.exists():
            existing = pd.read_csv(ledger_path)
        else:
            existing = pd.DataFrame(columns=out.columns)
    except Exception:
        existing = pd.DataFrame(columns=out.columns)

    # Combine avoiding re-adding rows that already exist in the ledger
    if len(existing) == 0:
        combined = out.copy()
    else:
        existing_ids = set(existing["transaction_id"].astype(str))
        out_filtered = out[~out["transaction_id"].astype(str).isin(existing_ids)]
        combined = pd.concat([existing, out_filtered], ignore_index=True)

    combined = (
        combined[STANDARD_FIELDS]
        .sort_values(by=["date", "amount", "description"])
        .reset_index(drop=True)
    )

    # Event sourcing dual-write: emit TransactionImported events for new transactions
    if event_store is not None:
        from gilt.model.events import TransactionDescriptionObserved

        existing_ids = set(existing["transaction_id"].astype(str)) if len(existing) > 0 else set()

        # Build index of existing transactions by (date, amount, account_id)
        existing_by_key = {}
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
                    except (ValueError, Exception):
                        pass  # Skip events that can't be created

            # Only emit TransactionImported events for new transactions
            if txn_id not in existing_ids:
                raw_row = {}  # Simplified for now as mapping back is complex after sort

                try:
                    event = TransactionImported(
                        transaction_date=str(row["date"]),
                        transaction_id=txn_id,
                        source_file=input_path.name,
                        source_account=account_id,
                        raw_description=str(row["description"]),
                        amount=Decimal(str(row["amount"])),
                        currency=str(row["currency"]),
                        raw_data=raw_row,
                    )
                    event_store.append_event(event)
                except (ValueError, Exception):
                    # Skip events that can't be created (invalid data)
                    continue

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
