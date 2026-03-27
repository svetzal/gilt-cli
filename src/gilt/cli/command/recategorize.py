from __future__ import annotations

import typer
from rich.table import Table

from gilt.model.account import TransactionGroup
from gilt.model.category_io import parse_category_path
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

from .util import console, fmt_amount_str, print_dry_run_message

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
        console.print("[red]Error:[/] --from category cannot be empty")
        return 1

    if not to_cat:
        console.print("[red]Error:[/] --to category cannot be empty")
        return 1

    # Check projections database exists
    if not workspace.projections_path.exists():
        console.print(
            f"[red]Error:[/red] Projections database not found at {workspace.projections_path}\n"
            "[dim]Run 'gilt rebuild-projections' first[/dim]"
        )
        return 1

    # Load transactions from projections (excludes duplicates)
    projection_builder = ProjectionBuilder(workspace.projections_path)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    if not all_transactions:
        console.print("[yellow]No transactions found in projections database[/]")
        return 0

    # Find matches by category/subcategory
    total_matched = 0
    all_matches: list[tuple[str, TransactionGroup]] = []  # (account_id, group)

    for row in all_transactions:
        # Match category
        if row.get("category") != from_cat:
            continue

        # Match subcategory if specified in --from
        if from_subcat is not None and row.get("subcategory") != from_subcat:
            continue

        # Convert row to TransactionGroup
        group = TransactionGroup.from_projection_row(row)
        all_matches.append((row["account_id"], group))
        total_matched += 1

    if total_matched == 0:
        console.print(f"[yellow]No transactions found with category '{from_category}'[/]")
        return 0

    # Show what will be renamed
    _display_matches(all_matches, from_category, to_category)

    if not write:
        print_dry_run_message()
        return 0

    # Confirm
    import sys

    if sys.stdin.isatty() and not typer.confirm(
        f"Rename category in {total_matched} transaction(s)?"
    ):
        console.print("Cancelled")
        return 0

    # Apply renaming by account
    _apply_renaming(all_matches, to_cat, to_subcat, workspace)

    console.print(f"[green]✓[/] Renamed category in {total_matched} transaction(s)")
    return 0


def _display_matches(
    matches: list[tuple[str, TransactionGroup]],
    from_category: str,
    to_category: str,
) -> None:
    """Display matched transactions in a table."""
    table = Table(title="Transactions to Recategorize", show_lines=False)
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("TxnID", style="blue", no_wrap=True)
    table.add_column("Date", style="white")
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("From", style="red")
    table.add_column("→ To", style="green")

    for account_id, group in matches[:50]:  # Limit display to 50
        t = group.primary

        current_cat = from_category
        new_cat = to_category

        table.add_row(
            account_id,
            t.transaction_id[:8],
            str(t.date),
            (t.description or "")[:40],
            fmt_amount_str(t.amount),
            current_cat,
            new_cat,
        )

    console.print(table)

    if len(matches) > 50:
        console.print(f"[dim]... and {len(matches) - 50} more[/]")

    console.print(f"\n[bold]Total:[/] {len(matches)} transaction(s)")


def _apply_renaming(
    matches: list[tuple[str, TransactionGroup]],
    to_cat: str,
    to_subcat: str | None,
    workspace: Workspace,
) -> None:
    """Apply category renaming to matched transactions.

    Args:
        matches: List of (account_id, group) tuples
        to_cat: New category name
        to_subcat: New subcategory name (or None)
        workspace: Workspace for resolving data paths
    """
    from gilt.services.categorization_persistence_service import CategorizationPersistenceService

    event_store = EventStore(workspace.event_store_path)
    projection_builder = ProjectionBuilder(workspace.projections_path)

    persistence_svc = CategorizationPersistenceService(
        event_store=event_store,
        projection_builder=projection_builder,
        ledger_data_dir=workspace.ledger_data_dir,
    )
    persistence_svc.persist_category_rename(
        matches=matches,
        to_category=to_cat,
        to_subcategory=to_subcat,
    )


__all__ = ["run"]
