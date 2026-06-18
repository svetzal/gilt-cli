"""Column detection and mapping for bank CSV files.

Pure functions — no I/O or side effects.
"""

from __future__ import annotations

import pandas as pd


def _first_match(name_candidates: list[str], available: list[str]) -> str | None:
    """Return the first candidate found (case-insensitive) in available column names."""
    lower_map = {c.lower(): c for c in available}
    for cand in name_candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


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


def find_missing_columns(column_map: dict, overrides: dict) -> list[str]:
    """Return names of required logical column roles absent from column_map and overrides.

    Pure function: checks whether "date", "description", and "amount" roles can be
    resolved from the given column_map dict and RBC-override dict. Returns a list of
    the missing role names (empty list means all required columns are present).
    """
    missing: list[str] = []
    if column_map.get("date") is None and "date_series" not in overrides:
        missing.append("date")
    if (
        column_map.get("desc1") is None
        and column_map.get("desc2") is None
        and "desc1_series" not in overrides
        and "desc2_series" not in overrides
    ):
        missing.append("description")
    if (
        column_map.get("amount") is None
        and column_map.get("usd") is None
        and "amount_series" not in overrides
    ):
        missing.append("amount")
    return missing
