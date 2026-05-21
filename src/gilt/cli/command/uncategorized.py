from __future__ import annotations

"""
Display uncategorized transactions.
"""


from gilt.model.account import Transaction
from gilt.workspace import Workspace

from .util import (
    build_transaction_table,
    console,
    find_by_account,
    find_uncategorized,
    fmt_amount_str,
    require_projections,
)


def _filter_transactions(filtered_rows: list, year: int | None, min_amount: float | None) -> list[Transaction]:
    """Apply year and min_amount filters and convert rows to Transaction objects."""
    result: list[Transaction] = []
    for row in filtered_rows:
        txn = Transaction.from_projection_row(row)
        if year is not None and txn.date.year != year:
            continue
        if min_amount is not None and abs(txn.amount) < min_amount:
            continue
        result.append(txn)
    return result


def _display_uncategorized_table(console, displayed: list[Transaction], year: int | None) -> None:
    """Build and print the uncategorized transactions table."""
    title = "Uncategorized Transactions"
    if year:
        title += f" ({year})"

    table = build_transaction_table(title, [("Notes", {"style": "dim"})])

    for txn in displayed:
        table.add_row(
            txn.account_id,
            txn.transaction_id[:8],
            str(txn.date),
            (txn.description or "")[:50],
            fmt_amount_str(txn.amount),
            (txn.notes or "")[:30],
        )

    console.print(table)


def _display_summary(console, total_count: int, limit: int | None, remaining: int) -> None:
    """Print the summary line and optional limit notice."""
    console.print(f"\n[bold]Total uncategorized:[/] {total_count} transaction(s)")
    if remaining > 0:
        console.print(f"[dim]Showing first {limit}, {remaining} more not displayed[/]")
    console.print("\n[dim]Tip: Use 'gilt categorize' to assign categories[/]")


def run(
    *,
    account: str | None = None,
    year: int | None = None,
    limit: int | None = None,
    min_amount: float | None = None,
    workspace: Workspace,
) -> int:
    """Display transactions without categories.

    Helps identify which transactions still need categorization.
    Sorted by description (for grouping similar transactions), then date.

    Loads from projections database, automatically excluding duplicates.

    Args:
        account: Optional account ID to filter
        year: Optional year to filter
        limit: Optional max number of transactions to show
        min_amount: Optional minimum absolute amount filter
        workspace: Workspace providing data paths

    Returns:
        Exit code (0 success, 1 error)
    """
    # Load projections
    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return 1

    # Filter
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)
    filtered_rows = find_by_account(find_uncategorized(all_transactions), account)
    uncategorized = _filter_transactions(filtered_rows, year, min_amount)

    if not uncategorized:
        console.print("[green]All transactions are categorized![/]")
        return 0

    # Sort
    uncategorized.sort(key=lambda x: (x.description or "", str(x.date)))

    # Limit
    if limit:
        displayed = uncategorized[:limit]
        remaining = len(uncategorized) - limit
    else:
        displayed = uncategorized
        remaining = 0

    # Display table
    _display_uncategorized_table(console, displayed, year)

    # Display summary
    _display_summary(console, len(uncategorized), limit, remaining)

    return 0
