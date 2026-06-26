"""Rich rendering functions for the summary command."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from gilt.model.account import Transaction
from gilt.services.summary_service import build_category_summary, build_subcategory_summary

from ..formatting import fmt_colored_amount

_DASH = "—"  # em-dash for None subcategory display


def _build_title(base: str, year: int | None, fy_label: str | None) -> str:
    if fy_label:
        return f"{base} ({fy_label.upper()})"
    if year:
        return f"{base} ({year})"
    return base


def display_category_table(
    con: Console,
    transactions: list[Transaction],
    year: int | None,
    fy_label: str | None,
    include_uncategorized: bool,
) -> None:
    title = _build_title("Category Summary", year, fy_label)
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Net", justify="right")

    rows = build_category_summary(transactions, include_uncategorized=include_uncategorized)

    if not rows:
        con.print("[dim]No categorized transactions found in the selected window.[/]")
        return

    for row in rows:
        label = row.category if row.category else f"[dim]{_DASH} uncategorized[/]"
        net_str = fmt_colored_amount(row.net)
        table.add_row(label, str(row.count), net_str)

    con.print(table)


def display_subcategory_table(
    con: Console,
    transactions: list[Transaction],
    category: str,
    year: int | None,
    fy_label: str | None,
) -> None:
    title = _build_title(f"Summary: {category}", year, fy_label)
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Subcategory", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Net", justify="right")
    table.add_column("% of Category", justify="right")

    category_total, rows = build_subcategory_summary(transactions, category)

    if not rows:
        con.print(
            f"[dim]No transactions found for category '{category}' in the selected window.[/]"
        )
        return

    for row in rows:
        label = row.subcategory if row.subcategory else f"[dim]{_DASH}[/]"
        net_str = fmt_colored_amount(row.net)
        pct_str = f"{row.pct_of_category:.1f}%"
        table.add_row(label, str(row.count), net_str, pct_str)

    con.print(table)

    total_str = fmt_colored_amount(category_total, bold=True)
    con.print(f"\n[bold]Category total ({category}):[/] {total_str}")
