"""Rich rendering functions for the budget command."""

from __future__ import annotations

from rich.table import Table

from gilt.services.budget_service import BudgetItem

from ..console import console
from ..formatting import fmt_amount_str


def display_budget_report(
    summary,
    year: int | None,
    month: int | None,
    category_filter: str | None,
) -> None:
    """Display the budget report table."""
    title = f"Budget Report: {category_filter}" if category_filter else "Budget Report"

    if year and month:
        title += f" ({year}-{month:02d})"
    elif year:
        title += f" ({year})"

    table = Table(title=title, show_lines=True)
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Subcategory", style="blue")
    table.add_column("Budget", style="green", justify="right")
    table.add_column("Actual", style="yellow", justify="right")
    table.add_column("Remaining", style="white", justify="right")
    table.add_column("% Used", style="magenta", justify="right")

    for item in summary.items:
        _add_budget_row_from_item(table, item)

    console.print(table)

    console.print(f"\n[bold]Total Budgeted:[/] ${summary.total_budgeted:,.2f}")
    console.print(f"[bold]Total Actual:[/] ${summary.total_actual:,.2f}")

    if summary.total_budgeted > 0:
        if summary.total_remaining >= 0:
            console.print(f"[bold]Remaining:[/] [green]${summary.total_remaining:,.2f}[/]")
        else:
            console.print(f"[bold]Over Budget:[/] [red]${abs(summary.total_remaining):,.2f}[/]")

        console.print(f"[bold]% Used:[/] {summary.percent_used:.1f}%")

    if summary.over_budget_count > 0:
        plural = "y" if summary.over_budget_count == 1 else "ies"
        console.print(f"\n[yellow]⚠ {summary.over_budget_count} categor{plural} over budget[/]")


def _add_budget_row_from_item(table: Table, item: BudgetItem) -> None:
    """Add a row to the budget table from a BudgetItem."""
    category_name = f"[bold]{item.category_name}[/]" if item.is_category_header else ""
    subcategory_name = f"  {item.subcategory_name}" if item.subcategory_name else ""

    budget_str = fmt_amount_str(item.budget_amount) if item.budget_amount else "—"

    if item.actual_amount > 0:
        if item.is_category_header:
            actual_str = f"[bold]{fmt_amount_str(item.actual_amount)}[/]"
        else:
            actual_str = fmt_amount_str(item.actual_amount)
    else:
        actual_str = "—"

    if item.remaining is not None:
        if item.remaining >= 0:
            remaining_str = f"[green]${item.remaining:,.2f}[/]"
        else:
            remaining_str = f"[red]-${abs(item.remaining):,.2f}[/]"
    else:
        remaining_str = "—"

    if item.percent_used is not None:
        if item.percent_used > 100:
            pct_str = f"[red bold]{item.percent_used:.1f}%[/]"
        elif item.percent_used > 90:
            pct_str = f"[yellow]{item.percent_used:.1f}%[/]"
        else:
            pct_str = f"[green]{item.percent_used:.1f}%[/]"
    else:
        pct_str = "—"

    table.add_row(
        category_name,
        subcategory_name,
        budget_str,
        actual_str,
        remaining_str,
        pct_str,
    )
