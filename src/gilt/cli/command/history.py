from __future__ import annotations

"""CLI command: show categorization history for a description pattern."""

from datetime import date

from rich.table import Table

from gilt.workspace import Workspace

from .util import console, fmt_amount, require_projections


def run(
    *,
    pattern: str,
    account: str | None = None,
    include_uncategorized: bool = False,
    limit: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
    workspace: Workspace,
) -> int:
    """Show categorization history for transactions matching a description pattern.

    Groups matching transactions by category/subcategory and displays counts,
    sums, min/max amounts, and the most recent date seen.

    Returns:
        0 on success (including empty results), 1 on missing projections, 2 on bad dates.
    """
    if date_from is not None:
        try:
            date.fromisoformat(date_from)
        except ValueError:
            console.print(f"[red]Error:[/] Invalid --date-from value: {date_from!r}")
            return 2

    if date_to is not None:
        try:
            date.fromisoformat(date_to)
        except ValueError:
            console.print(f"[red]Error:[/] Invalid --date-to value: {date_to!r}")
            return 2

    builder = require_projections(workspace)
    if builder is None:
        return 1

    rows = builder.find_category_history(
        pattern,
        account_id=account,
        include_uncategorized=include_uncategorized,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
    )

    if not rows:
        console.print(f"[yellow]No matching transactions for pattern '{pattern}'[/]")
        return 0

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
    return 0
