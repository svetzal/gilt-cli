"""Pure DataFrame ↔ domain model mapping for ingest.

Converts between pandas DataFrames and Transaction/TransactionGroup models.
No I/O or side effects.
"""

from __future__ import annotations

import pandas as pd

from gilt.model.account import Transaction, TransactionGroup
from gilt.model.ledger_io import STANDARD_FIELDS


def _opt_str(v) -> str | None:
    """Return None for NaN/None/empty values, otherwise return stripped string."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return s if s else None


def _groups_to_dataframe(groups: list[TransactionGroup]) -> pd.DataFrame:
    """Convert TransactionGroups to a STANDARD_FIELDS DataFrame (primary rows only)."""
    if not groups:
        return pd.DataFrame(columns=STANDARD_FIELDS)
    rows = [
        {
            "transaction_id": g.primary.transaction_id,
            "date": str(g.primary.date),
            "description": g.primary.description or "",
            "amount": g.primary.amount,
            "currency": g.primary.currency or "CAD",
            "account_id": g.primary.account_id,
            "counterparty": g.primary.counterparty,
            "category": g.primary.category,
            "subcategory": g.primary.subcategory,
            "notes": g.primary.notes,
            "source_file": g.primary.source_file or "",
        }
        for g in groups
    ]
    return pd.DataFrame(rows, columns=STANDARD_FIELDS)


def _dataframe_to_groups(df: pd.DataFrame) -> list[TransactionGroup]:
    """Convert a STANDARD_FIELDS DataFrame to single-primary TransactionGroups."""
    return build_groups_from_dataframe(df)


def build_groups_from_dataframe(df: pd.DataFrame) -> list[TransactionGroup]:
    """Convert a STANDARD_FIELDS DataFrame to single-primary TransactionGroups."""
    groups = []
    for _, row in df.iterrows():
        t = Transaction(
            transaction_id=str(row["transaction_id"]),
            date=str(row["date"]),
            description=str(row["description"] or ""),
            amount=float(row["amount"]) if pd.notna(row["amount"]) else 0.0,
            currency=str(row["currency"] or "CAD"),
            account_id=str(row["account_id"]),
            counterparty=_opt_str(row["counterparty"]),
            category=_opt_str(row["category"]),
            subcategory=_opt_str(row["subcategory"]),
            notes=_opt_str(row["notes"]),
            source_file=str(row["source_file"] or ""),
            metadata={},
        )
        groups.append(TransactionGroup(group_id=t.transaction_id, primary=t))
    return groups


def build_transactions_from_dataframe(df: pd.DataFrame) -> list[Transaction]:
    """Convert a STANDARD_FIELDS DataFrame to Transaction objects."""
    return [g.primary for g in build_groups_from_dataframe(df)]
