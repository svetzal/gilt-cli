from __future__ import annotations

from pathlib import Path

from gilt.cli.command._errors import CommandAbort
from gilt.cli.console import print_error
from gilt.cli.event_sourcing_bootstrap import require_projections
from gilt.cli.filtering import find_by_account
from gilt.model.account import Transaction
from gilt.services.transaction_query_service import TransactionFilter, TransactionQueryService
from gilt.workspace import Workspace


def load_ledger_text(ledger_path: Path) -> str:
    if not ledger_path.exists():
        raise FileNotFoundError(f"Ledger file not found: {ledger_path}")
    return ledger_path.read_text(encoding="utf-8")


def load_account_transactions(workspace: Workspace, account: str | None) -> list[dict]:
    """require_projections → get_all_transactions(include_duplicates=False) → find_by_account.

    Prints an error and raises CommandAbort(1) when projections are missing or when no
    transactions exist for the requested account.
    """
    projection_builder = require_projections(workspace)

    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)
    all_transactions = find_by_account(all_transactions, account)

    if account and not all_transactions:
        print_error(f"No transactions found for account '{account}'")
        raise CommandAbort(1)

    if not all_transactions:
        print_error("No transactions found in projections database")
        raise CommandAbort(1)

    return all_transactions


def load_all_transactions(
    workspace: Workspace,
    *,
    include_duplicates: bool,
) -> list[Transaction]:
    """require_projections → get_all_transactions → convert to Transaction objects.

    Raises CommandAbort(1) when projections are missing.
    """
    projection_builder = require_projections(workspace)
    rows = projection_builder.get_all_transactions(include_duplicates=include_duplicates)
    return [Transaction.from_projection_row(row) for row in rows]


def load_filtered_transactions(
    workspace: Workspace,
    criteria: TransactionFilter,
    *,
    include_duplicates: bool = False,
) -> list[Transaction]:
    """Load all transactions from projections and filter by the given criteria.

    Raises CommandAbort(1) when the projections database is missing or unavailable.
    Returns an empty list when there are no matching transactions.

    Args:
        workspace: Workspace providing the projections database path.
        criteria: Filter criteria applied via TransactionQueryService.find_matching.
        include_duplicates: When True, duplicate transactions are included in the load.

    Returns:
        Filtered Transaction list.
    """
    projection_builder = require_projections(workspace)
    rows = projection_builder.get_all_transactions(include_duplicates=include_duplicates)
    transactions = [Transaction.from_projection_row(row) for row in rows]
    return TransactionQueryService().find_matching(transactions, criteria)


__all__ = [
    "load_ledger_text",
    "load_account_transactions",
    "load_all_transactions",
    "load_filtered_transactions",
]
