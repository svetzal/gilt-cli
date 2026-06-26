"""Rich rendering functions for the rebuild-projections command."""

from __future__ import annotations

from rich.table import Table

from ..console import console


def display_rebuild_summary(
    transactions: list,
    duplicates: list,
) -> None:
    """Display the rebuild summary including account breakdown and enrichment stats."""
    num_duplicates = len(duplicates) - len(transactions)

    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Total transactions: {len(transactions)}")
    if num_duplicates > 0:
        console.print(f"  Duplicates detected: {num_duplicates}")

    accounts = {}
    for txn in transactions:
        account_id = txn["account_id"]
        accounts[account_id] = accounts.get(account_id, 0) + 1

    if accounts:
        console.print()
        table = Table(title="Transactions by Account")
        table.add_column("Account", style="cyan")
        table.add_column("Count", justify="right", style="green")

        for account_id in sorted(accounts.keys()):
            table.add_row(account_id, str(accounts[account_id]))

        console.print(table)

    evolved_count = sum(
        1
        for txn in transactions
        if txn.get("description_history") and len(eval(txn["description_history"])) > 1
    )

    if evolved_count > 0:
        console.print()
        console.print(f"[dim]ℹ {evolved_count} transactions have evolved descriptions[/dim]")

    enriched_count = sum(1 for txn in transactions if txn.get("vendor"))
    if enriched_count > 0:
        console.print(f"[dim]ℹ {enriched_count} transactions enriched with receipt data[/dim]")
