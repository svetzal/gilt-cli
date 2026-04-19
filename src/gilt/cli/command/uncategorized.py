from __future__ import annotations

"""
Display uncategorized transactions.
"""


from gilt.model.account import Transaction
from gilt.workspace import Workspace

from .util import (
    console,
    create_transaction_table,
    filter_by_account,
    filter_uncategorized,
    fmt_amount_str,
    require_projections,
)


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
    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return 1

    # Load all transactions from projections (excludes duplicates)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    # Filter for uncategorized transactions and by account
    filtered_rows = filter_by_account(filter_uncategorized(all_transactions), account)

    # Apply year and min_amount filters (unique to this command) and convert to Transaction objects
    uncategorized = []
    for row in filtered_rows:
        txn = Transaction.from_projection_row(row)

        # Filter by year if specified
        if year is not None and txn.date.year != year:
            continue

        # Filter by min_amount if specified
        if min_amount is not None and abs(txn.amount) < min_amount:
            continue

        uncategorized.append(txn)

    if not uncategorized:
        console.print("[green]All transactions are categorized![/]")
        return 0

    # Sort by description (for grouping), then date
    uncategorized.sort(key=lambda x: (x.description or "", str(x.date)))

    # Apply limit if specified
    if limit:
        displayed = uncategorized[:limit]
        remaining = len(uncategorized) - limit
    else:
        displayed = uncategorized
        remaining = 0

    # Build table
    title = "Uncategorized Transactions"
    if year:
        title += f" ({year})"

    table = create_transaction_table(title, [("Notes", {"style": "dim"})])

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

    # Summary
    console.print(f"\n[bold]Total uncategorized:[/] {len(uncategorized)} transaction(s)")
    if remaining > 0:
        console.print(f"[dim]Showing first {limit}, {remaining} more not displayed[/]")

    # Helpful hint
    console.print("\n[dim]Tip: Use 'gilt categorize' to assign categories[/]")

    return 0
