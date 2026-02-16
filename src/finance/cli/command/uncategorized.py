from __future__ import annotations

"""
Display uncategorized transactions.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from rich.table import Table

from .util import console
from finance.storage.projection import ProjectionBuilder
from finance.workspace import Workspace


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
        console.print(
            f"[red]Error:[/red] Projections database not found: {projections_path}"
        )
        console.print("[yellow]Run 'finance rebuild-projections' first.[/yellow]")
        return 1

    # Load all transactions from projections (excludes duplicates)
    projection_builder = ProjectionBuilder(projections_path)
    all_transactions = projection_builder.get_all_transactions(
        include_duplicates=False
    )

    # Filter for uncategorized transactions
    uncategorized = []

    for row in all_transactions:
        # Must not have category
        if row.get("category"):
            continue

        # Filter by account if specified
        if account and row["account_id"] != account:
            continue

        # Filter by year if specified
        if year is not None:
            txn_date = datetime.fromisoformat(row["transaction_date"]).date()
            if txn_date.year != year:
                continue

        # Filter by min_amount if specified
        if min_amount is not None:
            if abs(float(row["amount"])) < min_amount:
                continue

        uncategorized.append(row)

    if not uncategorized:
        console.print("[green]All transactions are categorized![/]")
        return 0

    # Sort by description (for grouping), then date
    uncategorized.sort(
        key=lambda x: (x["canonical_description"] or "", x["transaction_date"])
    )

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

    for row in displayed:
        txn_date = datetime.fromisoformat(row["transaction_date"]).date()
        table.add_row(
            row["account_id"],
            row["transaction_id"][:8],
            str(txn_date),
            (row["canonical_description"] or "")[:50],
            f"${float(row['amount']):,.2f}",
            (row.get("notes") or "")[:30],
        )

    console.print(table)

    # Summary
    console.print(
        f"\n[bold]Total uncategorized:[/] {len(uncategorized)} transaction(s)"
    )
    if remaining > 0:
        console.print(
            f"[dim]Showing first {limit}, {remaining} more not displayed[/]"
        )

    # Helpful hint
    console.print(
        "\n[dim]Tip: Use 'finance categorize' to assign categories[/]"
    )

    return 0
