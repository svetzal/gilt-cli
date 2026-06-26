"""
CLI command to manually mark a specific pair of transactions as duplicates.

Use this when you discover a duplicate that wasn't automatically detected
or when you want to mark a specific pair without reviewing all candidates.

Privacy:
- All processing happens on local files only.
- No network I/O.
"""

from __future__ import annotations

from gilt.services.duplicate_review_service import DuplicateReviewService
from gilt.services.transaction_operations_service import TransactionOperationsService
from gilt.workspace import Workspace

from ..console import console, print_error
from ..event_sourcing_bootstrap import require_event_sourcing, require_projections
from .mark_duplicate_review import prompt_description_choice
from .mark_duplicate_view import build_comparison_table, display_validation_results


def _persist_mark(
    review_service, ready, primary_txn: dict, duplicate_txn: dict, canonical_description: str
) -> int:
    """Emit the DuplicateConfirmed event and rebuild projections. Returns events_processed."""
    review_service.mark_manual_duplicate(
        primary_transaction_id=primary_txn["transaction_id"],
        duplicate_transaction_id=duplicate_txn["transaction_id"],
        canonical_description=canonical_description,
    )
    return ready.projection_builder.build_incremental(ready.event_store)


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
    ready = require_event_sourcing(workspace)

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
    display_validation_results(preparation.validation, write)
    if not preparation.validation.is_valid:
        return 1

    primary_txn = preparation.primary_txn
    duplicate_txn = preparation.duplicate_txn
    console.print(build_comparison_table(primary_txn, duplicate_txn))
    canonical_description = prompt_description_choice(primary_txn, duplicate_txn)

    if not write:
        console.print("[yellow]Dry-run mode:[/yellow]")
        console.print(
            f"  Would mark {duplicate_txn['transaction_id'][:8]} as duplicate of {primary_txn['transaction_id'][:8]}"
        )
        console.print(f"  Would use description: {canonical_description}")
        console.print("[dim]Use --write to persist changes[/dim]")
        return 0

    console.print("[dim]Rebuilding projections...[/dim]")
    events_processed = _persist_mark(
        review_service, ready, primary_txn, duplicate_txn, canonical_description
    )
    console.print()
    console.print("[green]✓ Duplicate marked successfully[/green]")
    console.print(f"  Primary: {primary_txn['transaction_id'][:8]}")
    console.print(
        f"  Duplicate: {duplicate_txn['transaction_id'][:8]} [dim](hidden from budgets)[/dim]"
    )
    console.print(f"  Description: {canonical_description}")
    console.print(f"  Events processed: {events_processed}")
    return 0
