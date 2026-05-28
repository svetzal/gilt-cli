from __future__ import annotations

"""
Display category/subcategory spending summary.
"""

from datetime import date

from rich.console import Console
from rich.table import Table

from gilt.model.account import Transaction
from gilt.services.summary_service import build_category_summary, build_subcategory_summary
from gilt.workspace import Workspace

from .util import console as _default_console
from .util import find_by_account, fmt_amount_str, require_projections

_DASH = "—"  # em-dash for None subcategory display


def _filter_by_date_window(
    rows: list[dict],
    year: int | None,
    fy_range: tuple[date, date] | None,
) -> list[Transaction]:
    """Convert projection rows to Transactions, applying date-window filter."""
    result: list[Transaction] = []
    for row in rows:
        txn = Transaction.from_projection_row(row)
        if year is not None and txn.date.year != year:
            continue
        if fy_range is not None and not (fy_range[0] <= txn.date <= fy_range[1]):
            continue
        result.append(txn)
    return result


def _build_title(base: str, year: int | None, fy_label: str | None) -> str:
    if fy_label:
        return f"{base} ({fy_label.upper()})"
    if year:
        return f"{base} ({year})"
    return base


def _display_category_table(
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
        amt = row.net
        if amt < 0:
            net_str = f"[red]{fmt_amount_str(amt)}[/]"
        elif amt > 0:
            net_str = f"[green]{fmt_amount_str(amt)}[/]"
        else:
            net_str = fmt_amount_str(amt)
        table.add_row(label, str(row.count), net_str)

    con.print(table)


def _display_subcategory_table(
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
        amt = row.net
        if amt < 0:
            net_str = f"[red]{fmt_amount_str(amt)}[/]"
        elif amt > 0:
            net_str = f"[green]{fmt_amount_str(amt)}[/]"
        else:
            net_str = fmt_amount_str(amt)
        pct_str = f"{row.pct_of_category:.1f}%"
        table.add_row(label, str(row.count), net_str, pct_str)

    con.print(table)

    # Footer: category total
    total_str: str
    if category_total < 0:
        total_str = f"[bold red]{fmt_amount_str(category_total)}[/]"
    elif category_total > 0:
        total_str = f"[bold green]{fmt_amount_str(category_total)}[/]"
    else:
        total_str = f"[bold]{fmt_amount_str(category_total)}[/]"

    con.print(f"\n[bold]Category total ({category}):[/] {total_str}")


def run(
    *,
    year: int | None = None,
    fy_range: tuple[date, date] | None = None,
    fy_label: str | None = None,
    account: str | None = None,
    category: str | None = None,
    include_uncategorized: bool = False,
    workspace: Workspace,
    _console: Console | None = None,
) -> int:
    """Display category or subcategory spending summary.

    Args:
        year: Calendar year filter (default: current year, unless fy_range given).
        fy_range: Fiscal year date range (overrides year).
        fy_label: Display label for fiscal year (e.g. "FY25").
        account: Optional account ID to restrict to.
        category: When provided, drill into this category's subcategories.
        include_uncategorized: Include a row for transactions with no category.
        workspace: Workspace providing data paths.
        _console: Optional Rich Console for testing.

    Returns:
        Exit code (0 success, 1 error).
    """
    con = _console if _console is not None else _default_console

    # Default to current calendar year when no window is specified
    effective_year = year
    if fy_range is None and year is None:
        effective_year = date.today().year

    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return 1

    all_rows = projection_builder.get_all_transactions(include_duplicates=False)
    account_rows = find_by_account(all_rows, account)
    transactions = _filter_by_date_window(account_rows, effective_year, fy_range)

    if category is not None:
        _display_subcategory_table(con, transactions, category, effective_year, fy_label)
    else:
        _display_category_table(con, transactions, effective_year, fy_label, include_uncategorized)

    return 0
