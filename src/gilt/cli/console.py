from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from gilt.cli.formatting import base_match_row
from gilt.cli.presentation import build_transaction_table
from gilt.model.account import TransactionGroup
from gilt.model.category_io import format_category_path

console = Console()


def print_error(message: str) -> None:
    console.print(f"[red]Error:[/] {message}")


def print_warning(message: str) -> None:
    console.print(f"[yellow]Warning:[/] {message}")


def print_error_list(heading: str, errors: list[str]) -> None:
    console.print(f"[red]{heading}:[/]")
    for error in errors:
        console.print(f"  • {error}")


def print_transaction_table(
    table: Table,
    total_count: int,
    *,
    display_limit: int = 50,
) -> None:
    """Print a transaction table and an overflow message if total_count exceeds display_limit.

    Args:
        table: The Rich Table to print.
        total_count: The true number of transactions (before any slice was applied).
        display_limit: Maximum rows shown before the overflow message is printed.
    """
    console.print(table)
    if total_count > display_limit:
        console.print(f"[dim]... and {total_count - display_limit} more[/]")


def print_dry_run_message(*, detail: str | None = None) -> None:
    """Print the standard dry-run warning. Call when write=False."""
    if detail:
        msg = f"Dry-run: use --write to persist {detail}"
    else:
        msg = "Dry-run: use --write to persist changes"
    console.print(f"[dim]{msg}[/dim]")


def print_match_total(n: int) -> None:
    """Print the standard 'Total: N transaction(s)' footer after a match table."""
    console.print(f"\n[bold]Total:[/] {n} transaction(s)")


def confirm_interactively(prompt: str) -> bool:
    """Return True when stdin is non-interactive (auto-proceed) or when the user confirms."""
    if not sys.stdin.isatty():
        return True
    return typer.confirm(prompt)


def display_transaction_matches(
    title: str,
    extra_columns: list[tuple[str, dict]],
    matches: Sequence,
    row_fn: Callable[[Any], tuple],
    *,
    display_limit: int = 50,
) -> None:
    """Create and print a transaction table for a sequence of matches.

    Args:
        title: Table title passed to ``build_transaction_table``.
        extra_columns: Extra column specs passed to ``build_transaction_table``.
        matches: The full sequence of matches. Only the first ``display_limit`` are rendered.
        row_fn: Callable that accepts a single match item and returns a tuple of column values
            matching (account, txn_id_prefix, date, description, amount, *extra_values).
        display_limit: Maximum rows to render before the overflow message is shown.
    """
    table = build_transaction_table(title, extra_columns)
    for item in matches[:display_limit]:
        table.add_row(*row_fn(item))
    print_transaction_table(table, len(matches), display_limit=display_limit)


def display_category_change_matches(
    title: str,
    from_header: str,
    to_header: str,
    matches: Sequence[tuple[str, TransactionGroup]],
    to_label: str,
    *,
    from_label: str | None = None,
) -> None:
    """Create and print a category-change transaction table.

    Each row shows the standard transaction columns plus a from-category column
    and a to-category column.  When ``from_label`` is supplied every row shows
    that fixed label in the from column; when it is ``None`` each row shows the
    transaction's current ``category:subcategory`` (or ``"—"`` when empty).

    Args:
        title: Table title.
        from_header: Column header for the "from" category column.
        to_header: Column header for the "to" category column.
        matches: Sequence of ``(account_id, TransactionGroup)`` pairs.
        to_label: Fixed label shown in the to column for every row.
        from_label: When supplied, shown as-is in the from column for every row.
    """

    def row_fn(item: tuple[str, TransactionGroup]) -> tuple:
        account_id, group = item
        t = group.primary
        if from_label is not None:
            from_col = from_label
        else:
            from_col = format_category_path(t.category or "", t.subcategory) or "—"
        return base_match_row(account_id, t) + (from_col, to_label)

    display_transaction_matches(
        title,
        [(from_header, {"style": "dim"}), (to_header, {"style": "green"})],
        matches,
        row_fn,
    )


__all__ = [
    "console",
    "print_error",
    "print_warning",
    "print_error_list",
    "print_transaction_table",
    "print_dry_run_message",
    "print_match_total",
    "confirm_interactively",
    "display_transaction_matches",
    "display_category_change_matches",
]
