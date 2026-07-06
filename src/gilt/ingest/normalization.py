"""Pure normalization functions for bank CSV data.

Handles date parsing, description combination, amount extraction,
and transaction ID computation. No I/O or side effects.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from gilt.ingest.column_mapping import _detect_rbc_overrides  # noqa: F401 (re-used internally)

# Frozen transaction_id hash spec: do not change without a migration plan.
HASH_ALGO_SPEC = (
    "v1: sha256 of 'account_id|date|amount|description' using values exactly as"
    " written to output columns (date in YYYY-MM-DD; amount via Python str();"
    " description as-is)."
)


def build_transaction_id(account_id: str, date: str, amount, description: str) -> str:
    base = f"{account_id}|{date}|{amount}|{description}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _build_date_series(
    df: pd.DataFrame, column_map: dict[str, str | None], overrides: dict[str, pd.Series]
) -> pd.Series:
    """Resolve and format the date series as YYYY-MM-DD strings.

    Uses the override series when present, otherwise reads from column_map["date"].
    Invalid dates are coerced to NaN.
    """
    raw = (
        overrides["date_series"]
        if "date_series" in overrides
        else df[column_map["date"]].astype(str).str.strip()
    )
    return pd.to_datetime(raw, errors="coerce", dayfirst=False).dt.strftime("%Y-%m-%d")


def _build_description_series(
    df: pd.DataFrame, column_map: dict[str, str | None], overrides: dict[str, pd.Series]
) -> pd.Series:
    """Resolve and combine desc1 and desc2 into a single description series.

    Parts are joined with " - " when both are non-empty. Returns stripped strings.
    """
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
    combined = d1.where(d2.eq(""), d1.str.cat(d2, sep=" - "))
    return combined.fillna("").astype(str).str.strip()


def _build_amount_series(
    df: pd.DataFrame,
    column_map: dict[str, str | None],
    overrides: dict[str, pd.Series],
    amount_sign: str,
) -> pd.Series:
    """Resolve the raw amount source, clean it, convert to numeric, and apply sign convention.

    Removes $, commas, and converts parenthesised values to negative.
    Negates the result when amount_sign is "expenses_positive".
    """
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
    amounts = pd.to_numeric(amt_str, errors="coerce")

    if amount_sign == "expenses_positive":
        amounts = -amounts

    return amounts


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

    out["date"] = _build_date_series(df, column_map, overrides)
    out["description"] = _build_description_series(df, column_map, overrides)
    out["amount"] = _build_amount_series(df, column_map, overrides, amount_sign)

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
        lambda row: build_transaction_id(
            row["account_id"], row["date"], row["amount"], row["description"]
        ),
        axis=1,
    )

    return out
