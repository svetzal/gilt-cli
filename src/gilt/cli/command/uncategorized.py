from __future__ import annotations

"""
Display uncategorized transactions.
"""

from typing import Optional

from rich.table import Table

from .util import console
from gilt.model.account import Transaction
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def run(
    *,
    account: Optional[str] = None,
    year: Optional[int] = None,
    limit: Optional[int] = None,
    min_amount: Optional[float] = None,
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
    projections_path = workspace.projections_path

    # Check projections exist
    if not projections_path.exists():
        console.print(f"[red]Error:[/red] Projections database not found: {projections_path}")
        console.print("[yellow]Run 'gilt rebuild-projections' first.[/yellow]")
        return 1

    # Load all transactions from projections (excludes duplicates)
    projection_builder = ProjectionBuilder(projections_path)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    # Filter for uncategorized transactions
    uncategorized = []

    for row in all_transactions:
        # Must not have category
        if row.get("category"):
            continue

        # Convert to Transaction object for filtered rows
        txn = Transaction.from_projection_row(row)

        # Filter by account if specified
        if account and txn.account_id != account:
            continue

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

    table = Table(title=title, show_lines=False)
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("TxnID", style="blue", no_wrap=True)
    table.add_column("Date", style="white")
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("Notes", style="dim")

    for txn in displayed:
        table.add_row(
            txn.account_id,
            txn.transaction_id[:8],
            str(txn.date),
            (txn.description or "")[:50],
            f"${txn.amount:,.2f}",
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
