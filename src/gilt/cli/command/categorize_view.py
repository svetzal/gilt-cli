"""Rich rendering functions for the categorize command.

All functions in this module perform console output only — no I/O,
no user prompts, no business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gilt.model.category_io import format_category_path

from ..console import console, display_category_change_matches, display_transaction_matches
from ..formatting import category_preview_row

if TYPE_CHECKING:
    from gilt.model.account import TransactionGroup

    from .categorize import ResolvedEntry


def display_categorization_matches(
    matches: list[tuple[str, TransactionGroup]],
    category: str,
    subcategory: str | None,
) -> None:
    """Display matched transactions in a category-change table."""
    display_category_change_matches(
        "Matched Transactions",
        "Current Cat",
        "→ New Cat",
        matches,
        format_category_path(category, subcategory),
    )


def display_batch_preview(
    preview_matches: list[tuple[str, TransactionGroup]],
    resolved: list[ResolvedEntry],
) -> None:
    """Display a preview table for file-batch categorizations."""
    cat_by_txn = {e.transaction_id: (e.category, e.subcategory) for e in resolved}

    def row_fn(item: tuple[str, TransactionGroup]) -> tuple:
        account_id, group = item
        t = group.primary
        cat, subcat = cat_by_txn.get(t.transaction_id, (t.category or "", t.subcategory))
        return category_preview_row(account_id, t, format_category_path(cat, subcat))

    display_transaction_matches(
        "Batch Categorization Preview",
        [("→ Category", {"style": "green"})],
        preview_matches,
        row_fn,
    )


def report_categorization_result(
    all_matches: list[tuple[str, TransactionGroup]],
    result: int,
    recategorized_count: int,
    write: bool,
) -> int:
    """Print categorization success/warning messages. Returns result unchanged."""
    if result == 0 and write:
        if recategorized_count > 0:
            console.print(
                f"[yellow]Warning:[/] {recategorized_count} transaction(s) already had a category "
                f"and were re-categorized"
            )
        console.print(f"[green]✓[/] Categorized {len(all_matches)} transaction(s)")
    return result


def print_no_entries() -> None:
    """Print a notice that no entries were found in batch input."""
    console.print("[yellow]No entries found in batch input[/]")


def print_no_matches() -> None:
    """Print a notice that no matching transactions were found."""
    console.print("[yellow]No matching transactions found[/]")


def print_batch_mode_notice(count: int) -> None:
    """Print a batch-mode notice with the match count."""
    console.print(
        f"[yellow]Batch mode:[/] {count} transactions would be categorized. "
        f"Use --yes to auto-confirm (dry-run)"
    )


def print_categorized_success(count: int) -> None:
    """Print a success message after categorization."""
    console.print(f"[green]✓[/] Categorized {count} transaction(s)")


def print_category_warning(msg: str) -> None:
    """Print a yellow warning for a category path issue."""
    console.print(f"[yellow]Warning:[/] {msg}")


def print_category_add_hint(category: str) -> None:
    """Print a hint to add the missing category."""
    console.print(f"Add it first: gilt category --add '{category}' --write")


__all__ = [
    "display_categorization_matches",
    "display_batch_preview",
    "report_categorization_result",
    "print_no_entries",
    "print_no_matches",
    "print_batch_mode_notice",
    "print_categorized_success",
    "print_category_warning",
    "print_category_add_hint",
]
