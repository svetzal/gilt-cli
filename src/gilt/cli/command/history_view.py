"""Rich rendering functions for the history command."""

from __future__ import annotations

from rich.table import Table

from ..console import console
from ..formatting import fmt_amount


def display_history_table(
    rows, pattern: str, account: str | None, date_from: str | None, date_to: str | None
) -> None:
    """Build and print the category history table."""
    title = f"History for '{pattern}'"
    if account:
        title += f" — account {account}"
    if date_from or date_to:
        window = f"{date_from or '...'} → {date_to or '...'}"
        title += f" — {window}"

    table = Table(title=title, show_lines=False)
    table.add_column("Category", style="yellow")
    table.add_column("Subcategory", style="yellow")
    table.add_column("Count", justify="right", style="cyan")
    table.add_column("Sum", justify="right")
    table.add_column("Min", justify="right")
    table.add_column("Max", justify="right")
    table.add_column("Latest", style="dim", no_wrap=True)

    for row in rows:
        cat_display = row.category or "(uncategorized)"
        sub_display = row.subcategory or ""
        table.add_row(
            cat_display,
            sub_display,
            str(row.count),
            fmt_amount(row.total),
            fmt_amount(row.min_amount),
            fmt_amount(row.max_amount),
            row.latest_date or "",
        )

    console.print(table)
