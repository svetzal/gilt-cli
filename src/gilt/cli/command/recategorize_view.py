"""Rich rendering functions for the recategorize command.

All functions in this module perform console output only — no I/O,
no user prompts, no business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..console import console, display_category_change_matches

if TYPE_CHECKING:
    from gilt.model.account import TransactionGroup


def display_recategorize_matches(
    matches: list[tuple[str, TransactionGroup]],
    from_label: str | None,
    to_category: str,
) -> None:
    """Display matched transactions in a recategorize table.

    When from_label is None (selection mode without explicit --from),
    the "From" column shows the transaction's current category.
    """
    display_category_change_matches(
        "Transactions to Recategorize",
        "From",
        "→ To",
        matches,
        to_category,
        from_label=from_label,
    )


def print_no_transactions_for_category(from_category: str) -> None:
    """Print a notice that no transactions were found with the given category."""
    console.print(f"[yellow]No transactions found with category '{from_category}'[/]")


def print_no_filter_matches() -> None:
    """Print a notice that no transactions match the given filters."""
    console.print("[yellow]No transactions match the given filters[/]")


def print_renamed_success(count: int) -> None:
    """Print a success message after renaming a category."""
    console.print(f"[green]✓[/] Renamed category in {count} transaction(s)")


def print_recategorized_success(count: int) -> None:
    """Print a success message after recategorizing transactions."""
    console.print(f"[green]✓[/] Recategorized {count} transaction(s)")


__all__ = [
    "display_recategorize_matches",
    "print_no_transactions_for_category",
    "print_no_filter_matches",
    "print_renamed_success",
    "print_recategorized_success",
]
