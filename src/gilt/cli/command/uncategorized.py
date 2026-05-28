from __future__ import annotations

"""
Display uncategorized transactions.
"""

from collections import Counter
from datetime import date

from rich.console import Console
from rich.table import Table

from gilt.model.account import Transaction
from gilt.workspace import Workspace

from .util import (
    build_transaction_table,
    find_by_account,
    find_uncategorized,
    fmt_amount_str,
    require_projections,
)
from .util import (
    console as _default_console,
)


def _filter_transactions(
    filtered_rows: list,
    year: int | None,
    min_amount: float | None,
    fy_range: tuple[date, date] | None = None,
) -> list[Transaction]:
    """Apply year, fy_range, and min_amount filters and convert rows to Transaction objects."""
    result: list[Transaction] = []
    for row in filtered_rows:
        txn = Transaction.from_projection_row(row)
        if year is not None and txn.date.year != year:
            continue
        if fy_range is not None and not (fy_range[0] <= txn.date <= fy_range[1]):
            continue
        if min_amount is not None and abs(txn.amount) < min_amount:
            continue
        result.append(txn)
    return result


def _display_uncategorized_table(
    con: Console,
    displayed: list[Transaction],
    year: int | None,
    fy_label: str | None = None,
) -> None:
    """Build and print the uncategorized transactions table."""
    title = "Uncategorized Transactions"
    if fy_label:
        title += f" ({fy_label.upper()})"
    elif year:
        title += f" ({year})"

    table = build_transaction_table(title, [("Notes", {"style": "dim"})])

    for txn in displayed:
        table.add_row(
            txn.account_id,
            txn.transaction_id[:8],
            str(txn.date),
            (txn.description or "")[:60],
            fmt_amount_str(txn.amount),
            (txn.notes or "")[:30],
        )

    con.print(table)


def _display_account_summary(con: Console, transactions: list[Transaction]) -> None:
    """Print a per-account count summary table."""
    counts: Counter[str] = Counter(txn.account_id for txn in transactions)
    table = Table(title="By Account", show_header=True, header_style="bold")
    table.add_column("Account", style="cyan")
    table.add_column("Count", justify="right")
    for account_id in sorted(counts):
        table.add_row(account_id, str(counts[account_id]))
    con.print(table)


def _display_summary(
    con: Console,
    total_count: int,
    limit: int | None,
    remaining: int,
    transactions: list[Transaction],
) -> None:
    """Print the per-account summary, total line, and optional limit notice."""
    _display_account_summary(con, transactions)
    con.print(f"\n[bold]Total uncategorized:[/] {total_count} transaction(s)")
    if remaining > 0:
        con.print(f"[dim]Showing first {limit}, {remaining} more not displayed[/]")
    con.print("\n[dim]Tip: Use 'gilt categorize' to assign categories[/]")


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

    # Load projections
    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return 1

    # Filter
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)
    filtered_rows = find_by_account(find_uncategorized(all_transactions), account)
    uncategorized = _filter_transactions(filtered_rows, year, min_amount, fy_range)

    if not uncategorized:
        con.print("[green]All transactions are categorized![/]")
        return 0

    # Sort by (account_id, date)
    uncategorized.sort(key=lambda x: (x.account_id, str(x.date)))

    # Limit
    if limit:
        displayed = uncategorized[:limit]
        remaining = len(uncategorized) - limit
    else:
        displayed = uncategorized
        remaining = 0

    # Display table
    _display_uncategorized_table(con, displayed, year, fy_label)

    # Display per-account summary and total
    _display_summary(con, len(uncategorized), limit, remaining, uncategorized)

    return 0
