from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import typer
from rich.table import Table

from .util import console
from gilt.workspace import Workspace
from gilt.model.category_io import parse_category_path
from gilt.model.ledger_io import dump_ledger_csv, load_ledger_csv
from gilt.model.account import TransactionGroup
from gilt.storage.projection import ProjectionBuilder
from gilt.storage.event_store import EventStore
from gilt.model.events import TransactionCategorized


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
    all_matches: List[tuple[str, TransactionGroup]] = []  # (account_id, group)

    for row in all_transactions:
        # Match category
        if row.get("category") != from_cat:
            continue

        # Match subcategory if specified in --from
        if from_subcat is not None:
            if row.get("subcategory") != from_subcat:
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
        console.print("[dim]Dry-run: use --write to persist changes[/]")
        return 0

    # Confirm
    import sys

    if sys.stdin.isatty():
        if not typer.confirm(f"Rename category in {total_matched} transaction(s)?"):
            console.print("Cancelled")
            return 0

    # Apply renaming by account
    _apply_renaming(all_matches, to_cat, to_subcat, workspace)

    console.print(f"[green]✓[/] Renamed category in {total_matched} transaction(s)")
    return 0


def _display_matches(
    matches: List[tuple[str, TransactionGroup]],
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
            f"${t.amount:,.2f}",
            current_cat,
            new_cat,
        )

    console.print(table)

    if len(matches) > 50:
        console.print(f"[dim]... and {len(matches) - 50} more[/]")

    console.print(f"\n[bold]Total:[/] {len(matches)} transaction(s)")


def _apply_renaming(
    matches: List[tuple[str, TransactionGroup]],
    to_cat: str,
    to_subcat: Optional[str],
    workspace: Workspace,
) -> None:
    """Apply category renaming to matched transactions.

    Args:
        matches: List of (account_id, group) tuples
        to_cat: New category name
        to_subcat: New subcategory name (or None)
        workspace: Workspace for resolving data paths
    """
    data_dir = workspace.ledger_data_dir

    # Group by account
    by_account: dict[str, List[TransactionGroup]] = {}
    for account_id, group in matches:
        if account_id not in by_account:
            by_account[account_id] = []
        by_account[account_id].append(group)

    # Update each account's CSV
    for account_id, matched_groups in by_account.items():
        ledger_path = data_dir / f"{account_id}.csv"
        if not ledger_path.exists():
            console.print(f"[yellow]Warning: Ledger not found for {account_id}[/yellow]")
            continue

        # Reload full ledger
        text = ledger_path.read_text(encoding="utf-8")
        all_groups = load_ledger_csv(text, default_currency="CAD")

        # Update matched groups
        matched_ids = {g.primary.transaction_id for g in matched_groups}
        for group in all_groups:
            if group.primary.transaction_id in matched_ids:
                # Mutate in place since Transaction is mutable
                group.primary.category = to_cat
                # Only update subcategory if explicitly specified in --to
                if to_subcat is not None:
                    group.primary.subcategory = to_subcat

        # Write back
        updated_csv = dump_ledger_csv(all_groups)
        ledger_path.write_text(updated_csv, encoding="utf-8")

    # Emit TransactionCategorized events and rebuild projections
    event_store = EventStore(workspace.event_store_path)
    projection_builder = ProjectionBuilder(workspace.projections_path)

    for matched_groups in by_account.values():
        for group in matched_groups:
            event = TransactionCategorized(
                transaction_id=group.primary.transaction_id,
                category=to_cat,
                subcategory=to_subcat,
                source="user",  # Manual recategorization by user
                event_timestamp=datetime.now(),
            )
            event_store.append_event(event)

    # Rebuild projections incrementally to include new categorization events
    projection_builder.rebuild_incremental(event_store)


__all__ = ["run"]
