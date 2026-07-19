from __future__ import annotations

from gilt.model.account import Transaction, TransactionGroup


def group_by_account(rows: list[dict]) -> dict[str, list[TransactionGroup]]:
    """Group projection rows into TransactionGroup lists keyed by account_id."""
    groups_by_account: dict[str, list[TransactionGroup]] = {}
    for row in rows:
        account_id = row["account_id"]
        groups_by_account.setdefault(account_id, []).append(
            TransactionGroup.from_projection_row(row)
        )
    return groups_by_account


def match_from_row(row: dict) -> tuple[str, TransactionGroup]:
    """Build a (account_id, TransactionGroup) match tuple from a projection row dict."""
    return (row["account_id"], TransactionGroup.from_projection_row(row))


def match_from_transaction(t: Transaction) -> tuple[str, TransactionGroup]:
    """Build a (account_id, TransactionGroup) match tuple from a Transaction object."""
    return (t.account_id, TransactionGroup(group_id=t.transaction_id, primary=t))


def find_uncategorized(rows: list[dict]) -> list[dict]:
    return [row for row in rows if not row.get("category")]


def find_by_account(rows: list[dict], account: str | None) -> list[dict]:
    if account is None:
        return rows
    return [row for row in rows if row.get("account_id") == account]


__all__ = ["group_by_account", "match_from_row", "match_from_transaction", "find_uncategorized", "find_by_account"]
