"""
CLI command to manually mark a specific pair of transactions as duplicates.

Use this when you discover a duplicate that wasn't automatically detected
or when you want to mark a specific pair without reviewing all candidates.

Privacy:
- All processing happens on local files only.
- No network I/O.
"""

from __future__ import annotations

from rich.prompt import Prompt
from rich.table import Table

from gilt.services.duplicate_review_service import DuplicateReviewService
from gilt.services.transaction_operations_service import TransactionOperationsService
from gilt.workspace import Workspace

from .util import console, print_error, require_event_sourcing, require_projections


def _display_validation_results(validation, write: bool) -> None:
    """Display validation errors and warnings to the console."""
    for error in validation.errors:
        print_error(error)
    for warning in validation.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")
        if not write and ("different account" in warning or "different amount" in warning):
            console.print("[yellow]Use --write to proceed anyway[/yellow]")


def _build_comparison_table(primary_txn: dict, duplicate_txn: dict) -> Table:
    """Build a Rich table comparing the two transactions side by side."""
    table = Table(title="Mark Duplicate Transactions", show_header=True, show_lines=True)
    table.add_column("Field", style="cyan")
    table.add_column("Primary (Keep)", style="green")
    table.add_column("Duplicate (Hide)", style="red")
    table.add_row("ID", primary_txn["transaction_id"][:8], duplicate_txn["transaction_id"][:8])
    table.add_row("Date", str(primary_txn["transaction_date"]), str(duplicate_txn["transaction_date"]))
    table.add_row("Account", primary_txn["account_id"], duplicate_txn["account_id"])
    table.add_row("Amount", f"{float(primary_txn['amount']):.2f}", f"{float(duplicate_txn['amount']):.2f}")
    table.add_row("Description", primary_txn["canonical_description"], duplicate_txn["canonical_description"])
    return table


def _prompt_description_choice(primary_txn: dict, duplicate_txn: dict) -> str:
    """Display both description options, prompt for a choice, and return the canonical description."""
    console.print()
    console.print("[yellow]Which description would you like to keep?[/yellow]")
    console.print(f"  1) {primary_txn['canonical_description']} [green](primary)[/green]")
    console.print(f"  2) {duplicate_txn['canonical_description']} [red](duplicate)[/red]")
    console.print()
    choice = Prompt.ask("Description choice [1/2]", choices=["1", "2"], default="1", show_choices=False)
    canonical_description = (
        primary_txn["canonical_description"] if choice == "1" else duplicate_txn["canonical_description"]
    )
    console.print()
    return canonical_description


def _persist_mark(review_service, ready, primary_txn: dict, duplicate_txn: dict, canonical_description: str) -> None:
    """Emit the DuplicateConfirmed event, rebuild projections, and print success messages."""
    review_service.mark_manual_duplicate(
        primary_transaction_id=primary_txn["transaction_id"],
        duplicate_transaction_id=duplicate_txn["transaction_id"],
        canonical_description=canonical_description,
    )
    console.print("[dim]Rebuilding projections...[/dim]")
    events_processed = ready.projection_builder.rebuild_incremental(ready.event_store)
    console.print()
    console.print("[green]✓ Duplicate marked successfully[/green]")
    console.print(f"  Primary: {primary_txn['transaction_id'][:8]}")
    console.print(f"  Duplicate: {duplicate_txn['transaction_id'][:8]} [dim](hidden from budgets)[/dim]")
    console.print(f"  Description: {canonical_description}")
    console.print(f"  Events processed: {events_processed}")


def run(
    primary_txid: str,
    duplicate_txid: str,
    workspace: Workspace,
    write: bool = False,
) -> int:
    """Mark a specific pair of transactions as duplicates.

    Allows you to manually mark two transactions as duplicates without scanning
    through all candidates. Useful when you discover a duplicate in budget reports
    or transaction listings.

    Args:
        primary_txid: Transaction ID to keep (8+ char prefix)
        duplicate_txid: Transaction ID to mark as duplicate (8+ char prefix)
        workspace: Workspace for resolving data paths
        write: Persist changes (default: dry-run)

    Returns:
        Exit code (0 = success, 1 = error)

    Examples:
        # Preview marking a duplicate
        gilt mark-duplicate --primary a1b2c3d4 --duplicate e5f6g7h8

        # Confirm and persist
        gilt mark-duplicate --primary a1b2c3d4 --duplicate e5f6g7h8 --write
    """
    if not workspace.ledger_data_dir.exists():
        print_error(f"Data directory not found: {workspace.ledger_data_dir}")
        return 1
    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return 1
    ready = require_event_sourcing(workspace)
    if ready is None:
        return 1

    review_service = DuplicateReviewService(event_store=ready.event_store)
    tx_service = TransactionOperationsService()
    console.print("[dim]Looking up transactions...[/dim]")
    all_txns = projection_builder.get_all_transactions(include_duplicates=True)

    preparation = review_service.validate_and_prepare_mark(
        primary_txid, duplicate_txid, tx_service, all_txns
    )
    if isinstance(preparation, str):
        print_error(preparation)
        return 1
    _display_validation_results(preparation.validation, write)
    if not preparation.validation.is_valid:
        return 1

    primary_txn = preparation.primary_txn
    duplicate_txn = preparation.duplicate_txn
    console.print(_build_comparison_table(primary_txn, duplicate_txn))
    canonical_description = _prompt_description_choice(primary_txn, duplicate_txn)

    if not write:
        console.print("[yellow]Dry-run mode:[/yellow]")
        console.print(f"  Would mark {duplicate_txn['transaction_id'][:8]} as duplicate of {primary_txn['transaction_id'][:8]}")
        console.print(f"  Would use description: {canonical_description}")
        console.print("[dim]Use --write to persist changes[/dim]")
        return 0

    _persist_mark(review_service, ready, primary_txn, duplicate_txn, canonical_description)
    return 0
