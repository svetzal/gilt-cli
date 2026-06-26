from __future__ import annotations

"""
Display category/subcategory spending summary.
"""

from datetime import date

from rich.console import Console

from gilt.model.account import Transaction
from gilt.services.transaction_query_service import TransactionFilter, TransactionQueryService
from gilt.workspace import Workspace

from ..console import console as _default_console
from ..loaders import load_account_transactions
from .summary_view import display_category_table, display_subcategory_table


def run(
    *,
    year: int | None = None,
    fy_range: tuple[date, date] | None = None,
    fy_label: str | None = None,
    account: str | None = None,
    category: str | None = None,
    include_uncategorized: bool = False,
    workspace: Workspace,
    _console: Console | None = None,
) -> int:
    """Display category or subcategory spending summary.

    Args:
        year: Calendar year filter (default: current year, unless fy_range given).
        fy_range: Fiscal year date range (overrides year).
        fy_label: Display label for fiscal year (e.g. "FY25").
        account: Optional account ID to restrict to.
        category: When provided, drill into this category's subcategories.
        include_uncategorized: Include a row for transactions with no category.
        workspace: Workspace providing data paths.
        _console: Optional Rich Console for testing.

    Returns:
        Exit code (0 success, 1 error).
    """
    con = _console if _console is not None else _default_console

    effective_year = year
    if fy_range is None and year is None:
        effective_year = date.today().year

    account_rows = load_account_transactions(workspace, account)
    candidates = [Transaction.from_projection_row(row) for row in account_rows]
    criteria = TransactionFilter(year=effective_year, fy_range=fy_range)
    transactions = TransactionQueryService().find_matching(candidates, criteria)

    if category is not None:
        display_subcategory_table(con, transactions, category, effective_year, fy_label)
    else:
        display_category_table(con, transactions, effective_year, fy_label, include_uncategorized)

    return 0
