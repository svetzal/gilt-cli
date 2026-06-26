"""Rich rendering functions for the uncategorized command."""

from __future__ import annotations

from collections import Counter

from rich.console import Console
from rich.table import Table

from gilt.model.account import Transaction

from ..formatting import fmt_amount_str
from ..presentation import build_transaction_table


def display_uncategorized_table(
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


def display_account_summary(con: Console, transactions: list[Transaction]) -> None:
    """Print a per-account count summary table."""
    counts: Counter[str] = Counter(txn.account_id for txn in transactions)
    table = Table(title="By Account", show_header=True, header_style="bold")
    table.add_column("Account", style="cyan")
    table.add_column("Count", justify="right")
    for account_id in sorted(counts):
        table.add_row(account_id, str(counts[account_id]))
    con.print(table)


def display_summary(
    con: Console,
    total_count: int,
    limit: int | None,
    remaining: int,
    transactions: list[Transaction],
) -> None:
    """Print the per-account summary, total line, and optional limit notice."""
    display_account_summary(con, transactions)
    con.print(f"\n[bold]Total uncategorized:[/] {total_count} transaction(s)")
    if remaining > 0:
        con.print(f"[dim]Showing first {limit}, {remaining} more not displayed[/]")
    con.print("\n[dim]Tip: Use 'gilt categorize' to assign categories[/]")
