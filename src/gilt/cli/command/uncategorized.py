from __future__ import annotations

"""
Display uncategorized transactions.
"""

from datetime import date

from rich.console import Console

from gilt.model.account import Transaction
from gilt.services.transaction_query_service import TransactionFilter, TransactionQueryService
from gilt.workspace import Workspace

from ..console import console as _default_console
from ..filtering import find_uncategorized
from ..loaders import load_account_transactions
from .uncategorized_view import display_summary, display_uncategorized_table


def run(
    *,
    account: str | None = None,
    year: int | None = None,
    limit: int | None = None,
    min_amount: float | None = None,
    fy_range: tuple[date, date] | None = None,
    fy_label: str | None = None,
    workspace: Workspace,
    _console: Console | None = None,
) -> int:
    """Display transactions without categories.

    Helps identify which transactions still need categorization.
    Sorted by account_id, then date.

    Loads from projections database, automatically excluding duplicates.

    Args:
        account: Optional account ID to filter
        year: Optional calendar year to filter
        limit: Optional max number of transactions to show
        min_amount: Optional minimum absolute amount filter
        fy_range: Optional (start, end) date range for fiscal year filtering
        fy_label: Label string for the fiscal year (e.g. "FY25"), used in the title
        workspace: Workspace providing data paths
        _console: Optional Rich Console for testing (defaults to module-level console)

    Returns:
        Exit code (0 success, 1 error)
    """
    con = _console if _console is not None else _default_console

    all_rows = load_account_transactions(workspace, account)
    uncategorized_rows = find_uncategorized(all_rows)
    candidates = [Transaction.from_projection_row(row) for row in uncategorized_rows]
    criteria = TransactionFilter(year=year, fy_range=fy_range, min_abs_amount=min_amount)
    uncategorized = TransactionQueryService().find_matching(candidates, criteria)

    if not uncategorized:
        con.print("[green]All transactions are categorized![/]")
        return 0

    uncategorized.sort(key=lambda x: (x.account_id, str(x.date)))

    if limit:
        displayed = uncategorized[:limit]
        remaining = len(uncategorized) - limit
    else:
        displayed = uncategorized
        remaining = 0

    display_uncategorized_table(con, displayed, year, fy_label)
    display_summary(con, len(uncategorized), limit, remaining, uncategorized)

    return 0
