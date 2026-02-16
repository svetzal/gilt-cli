from __future__ import annotations

"""
Budget reporting: compare actual spending vs budgeted amounts.
"""

from datetime import date
from typing import Optional

from rich.table import Table

from .util import console
from gilt.services.budget_service import BudgetService, BudgetItem
from gilt.workspace import Workspace


def run(
    *,
    year: Optional[int] = None,
    month: Optional[int] = None,
    category: Optional[str] = None,
    workspace: Workspace,
) -> int:
    """Display budget summary comparing actual spending vs budgeted amounts.

    Shows spending by category for the specified period, with budget comparison
    when budgets are defined.

    Args:
        year: Filter by year (default: current year)
        month: Filter by month (1-12, requires year)
        category: Filter to specific category
        workspace: Workspace providing config and data paths

    Returns:
        Exit code (always 0)
    """
    # Default to current year if not specified
    if year is None and month is None:
        year = date.today().year

    # Validate month requires year
    if month is not None and year is None:
        console.print("[red]Error:[/] --month requires --year")
        return 1

    if month is not None and (month < 1 or month > 12):
        console.print("[red]Error:[/] --month must be between 1 and 12")
        return 1

    # Use BudgetService to get budget summary
    budget_service = BudgetService(workspace.ledger_data_dir, workspace.categories_config)

    try:
        summary = budget_service.get_budget_summary(
            year=year,
            month=month,
            category_filter=category,
        )
    except Exception as e:
        console.print(f"[red]Error:[/] Failed to generate budget report: {e}")
        return 1

    # Display report
    _display_budget_report(summary, year, month, category)

    return 0


def _display_budget_report(
    summary,
    year: Optional[int],
    month: Optional[int],
    category_filter: Optional[str],
) -> None:
    """Display the budget report table.

    Args:
        summary: BudgetSummary from BudgetService
        year: Filter year (for title)
        month: Filter month (for title)
        category_filter: Category filter (for title)
    """
    # Build title
    if category_filter:
        title = f"Budget Report: {category_filter}"
    else:
        title = "Budget Report"

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

    # Add rows from BudgetItems
    for item in summary.items:
        _add_budget_row_from_item(table, item)

    console.print(table)

    # Summary
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
    """Add a row to the budget table from a BudgetItem.

    Args:
        table: Rich table to add row to
        item: BudgetItem containing row data
    """
    # Format category name
    if item.is_category_header:
        category_name = f"[bold]{item.category_name}[/]"
    else:
        category_name = ""

    # Format subcategory name
    if item.subcategory_name:
        subcategory_name = f"  {item.subcategory_name}"
    else:
        subcategory_name = ""

    # Format budget
    budget_str = f"${item.budget_amount:,.2f}" if item.budget_amount else "—"

    # Format actual
    if item.actual_amount > 0:
        if item.is_category_header:
            actual_str = f"[bold]${item.actual_amount:,.2f}[/]"
        else:
            actual_str = f"${item.actual_amount:,.2f}"
    else:
        actual_str = "—"

    # Format remaining
    if item.remaining is not None:
        if item.remaining >= 0:
            remaining_str = f"[green]${item.remaining:,.2f}[/]"
        else:
            remaining_str = f"[red]-${abs(item.remaining):,.2f}[/]"
    else:
        remaining_str = "—"

    # Format percent used
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
