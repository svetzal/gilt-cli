from __future__ import annotations

import typer

from gilt.model.account import TransactionGroup
from gilt.model.category_io import parse_category_path
from gilt.workspace import Workspace

from .util import (
    console,
    display_transaction_matches,
    fmt_amount_str,
    print_dry_run_message,
    print_error,
    require_event_sourcing,
    require_persistence_service,
    require_projections,
)

"""
Rename categories across all ledger files.

Useful when renaming categories in categories.yml to update existing
transaction categorizations.
"""


def run(
    *,
    from_category: str,
    to_category: str,
    workspace: Workspace,
    write: bool = False,
) -> int:
    """Rename a category across all ledger files.

    Useful when renaming categories in categories.yml to update existing
    transaction categorizations. Does NOT validate the target category exists
    in config to support data migration scenarios.

    Args:
        from_category: Original category name (supports "Category:Subcategory" syntax)
        to_category: New category name (supports "Category:Subcategory" syntax)
        workspace: Workspace for resolving data paths
        write: Persist changes (default: dry-run)

    Returns:
        Exit code (0 success, 1 error)
    """
    # Parse category paths
    from_cat, from_subcat = parse_category_path(from_category)
    to_cat, to_subcat = parse_category_path(to_category)

    if not from_cat:
        print_error("--from category cannot be empty")
        return 1

    if not to_cat:
        print_error("--to category cannot be empty")
        return 1

    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return 1

    # Load transactions from projections (excludes duplicates)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    if not all_transactions:
        console.print("[yellow]No transactions found in projections database[/]")
        return 0

    all_matches = _find_matching_transactions(all_transactions, from_cat, from_subcat)
    total_matched = len(all_matches)

    if total_matched == 0:
        console.print(f"[yellow]No transactions found with category '{from_category}'[/]")
        return 0

    # Show what will be renamed
    _display_matches(all_matches, from_category, to_category)
    console.print(f"\n[bold]Total:[/] {total_matched} transaction(s)")

    if not write:
        print_dry_run_message()
        return 0

    return _confirm_and_apply_renaming(all_matches, to_cat, to_subcat, workspace, total_matched)


def _find_matching_transactions(
    all_transactions: list[dict],
    from_cat: str,
    from_subcat: str | None,
) -> list[tuple[str, TransactionGroup]]:
    """Find transactions matching the given category/subcategory. Returns (account_id, group) pairs."""
    matches: list[tuple[str, TransactionGroup]] = []
    for row in all_transactions:
        if row.get("category") != from_cat:
            continue
        if from_subcat is not None and row.get("subcategory") != from_subcat:
            continue
        group = TransactionGroup.from_projection_row(row)
        matches.append((row["account_id"], group))
    return matches


def _confirm_and_apply_renaming(
    all_matches: list[tuple[str, TransactionGroup]],
    to_cat: str,
    to_subcat: str | None,
    workspace: Workspace,
    total_matched: int,
) -> int:
    """Require event sourcing, confirm with user, and apply category renaming. Returns exit code."""
    ready = require_event_sourcing(workspace)
    if ready is None:
        return 1

    import sys

    if sys.stdin.isatty() and not typer.confirm(
        f"Rename category in {total_matched} transaction(s)?"
    ):
        console.print("Cancelled")
        return 0

    _apply_renaming(all_matches, to_cat, to_subcat, ready, workspace)
    console.print(f"[green]✓[/] Renamed category in {total_matched} transaction(s)")
    return 0


def _display_matches(
    matches: list[tuple[str, TransactionGroup]],
    from_category: str,
    to_category: str,
) -> None:
    """Display matched transactions in a table."""

    def row_fn(item: tuple[str, TransactionGroup]) -> tuple:
        account_id, group = item
        t = group.primary
        return (
            account_id,
            t.transaction_id[:8],
            str(t.date),
            (t.description or "")[:40],
            fmt_amount_str(t.amount),
            from_category,
            to_category,
        )

    display_transaction_matches(
        "Transactions to Recategorize",
        [("From", {"style": "red"}), ("→ To", {"style": "green"})],
        matches,
        row_fn,
    )


def _apply_renaming(
    matches: list[tuple[str, TransactionGroup]],
    to_cat: str,
    to_subcat: str | None,
    ready,
    workspace: Workspace,
) -> None:
    """Apply category renaming to matched transactions."""
    persistence_svc = require_persistence_service(ready, workspace)
    persistence_svc.persist_category_rename(
        matches=matches,
        to_category=to_cat,
        to_subcategory=to_subcat,
    )


__all__ = ["run"]
