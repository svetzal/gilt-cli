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

from .util import console, require_event_sourcing, require_projections


def _resolve_prefix(tx_service: TransactionOperationsService, txid_prefix: str, transactions: list[dict]) -> dict | None:
    """Resolve a transaction by prefix, printing errors to console.

    Returns the transaction dict on success, None on any error.
    """
    result = tx_service.find_by_prefix(txid_prefix, transactions)
    if result.transaction is not None:
        return result.transaction
    if result.error == "prefix_too_short":
        console.print(
            f"[red]Error:[/red] Transaction ID prefix must be at least 8 characters "
            f"(got {len(txid_prefix)})"
        )
    elif result.error == "not_found":
        console.print(f"[red]Error:[/red] No transaction found with ID prefix: {txid_prefix}")
    elif result.error == "ambiguous":
        console.print(
            f"[red]Error:[/red] Ambiguous transaction ID prefix '{txid_prefix}' "
            f"matches {len(result.ambiguous_matches)} transactions:"
        )
        for tid in (result.ambiguous_matches or []):
            console.print(f"  - {tid}")
    return None


def _display_validation_results(validation, write: bool) -> None:
    """Display validation errors and warnings to the console."""
    for error in validation.errors:
        console.print(f"[red]Error:[/red] {error}")

    for warning in validation.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")
        if not write and ("different account" in warning or "different amount" in warning):
            console.print("[yellow]Use --write to proceed anyway[/yellow]")


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
        console.print(f"[red]Error:[/red] Data directory not found: {workspace.ledger_data_dir}")
        return 1

    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return 1

    # Validate input
    if primary_txid == duplicate_txid:
        console.print("[red]Error:[/red] Primary and duplicate transaction IDs must be different")
        return 1

    # Initialize services
    ready = require_event_sourcing(workspace)
    if ready is None:
        return 1
    event_store = ready.event_store
    review_service = DuplicateReviewService(event_store=event_store)
    tx_service = TransactionOperationsService()

    # Find transactions
    console.print("[dim]Looking up transactions...[/dim]")
    all_txns = projection_builder.get_all_transactions(include_duplicates=True)

    primary_txn = _resolve_prefix(tx_service, primary_txid, all_txns)
    if not primary_txn:
        return 1

    duplicate_txn = _resolve_prefix(tx_service, duplicate_txid, all_txns)
    if not duplicate_txn:
        return 1

    validation = review_service.validate_duplicate_pair(primary_txn, duplicate_txn)
    _display_validation_results(validation, write)
    if not validation.is_valid:
        return 1

    # Display both transactions
    table = Table(
        title="Mark Duplicate Transactions",
        show_header=True,
        show_lines=True,
    )

    table.add_column("Field", style="cyan")
    table.add_column("Primary (Keep)", style="green")
    table.add_column("Duplicate (Hide)", style="red")

    table.add_row(
        "ID",
        primary_txn["transaction_id"][:8],
        duplicate_txn["transaction_id"][:8],
    )
    table.add_row(
        "Date",
        str(primary_txn["transaction_date"]),
        str(duplicate_txn["transaction_date"]),
    )
    table.add_row(
        "Account",
        primary_txn["account_id"],
        duplicate_txn["account_id"],
    )
    table.add_row(
        "Amount",
        f"{float(primary_txn['amount']):.2f}",
        f"{float(duplicate_txn['amount']):.2f}",
    )
    table.add_row(
        "Description",
        primary_txn["canonical_description"],
        duplicate_txn["canonical_description"],
    )

    console.print(table)
    console.print()

    # Prompt for canonical description
    console.print("[yellow]Which description would you like to keep?[/yellow]")
    console.print(f"  1) {primary_txn['canonical_description']} [green](primary)[/green]")
    console.print(f"  2) {duplicate_txn['canonical_description']} [red](duplicate)[/red]")
    console.print()

    choice = Prompt.ask(
        "Description choice [1/2]",
        choices=["1", "2"],
        default="1",
        show_choices=False,
    )

    if choice == "1":
        canonical_description = primary_txn["canonical_description"]
    else:
        canonical_description = duplicate_txn["canonical_description"]

    console.print()

    if not write:
        console.print("[yellow]Dry-run mode:[/yellow]")
        dup_id = duplicate_txn["transaction_id"][:8]
        pri_id = primary_txn["transaction_id"][:8]
        console.print(f"  Would mark {dup_id} as duplicate of {pri_id}")
        console.print(f"  Would use description: {canonical_description}")
        console.print()
        console.print("[dim]Use --write to persist changes[/dim]")
        return 0

    # Emit DuplicateConfirmed event
    review_service.mark_manual_duplicate(
        primary_transaction_id=primary_txn["transaction_id"],
        duplicate_transaction_id=duplicate_txn["transaction_id"],
        canonical_description=canonical_description,
    )

    # Rebuild projections to reflect the change
    console.print("[dim]Rebuilding projections...[/dim]")
    events_processed = ready.projection_builder.rebuild_incremental(event_store)

    console.print()
    console.print("[green]✓ Duplicate marked successfully[/green]")
    console.print(f"  Primary: {primary_txn['transaction_id'][:8]}")
    dup_id = duplicate_txn["transaction_id"][:8]
    console.print(f"  Duplicate: {dup_id} [dim](hidden from budgets)[/dim]")
    console.print(f"  Description: {canonical_description}")
    console.print(f"  Events processed: {events_processed}")

    return 0
