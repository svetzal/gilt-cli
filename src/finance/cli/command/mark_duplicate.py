"""
CLI command to manually mark a specific pair of transactions as duplicates.

Use this when you discover a duplicate that wasn't automatically detected
or when you want to mark a specific pair without reviewing all candidates.

Privacy:
- All processing happens on local files only.
- No network I/O.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from finance.workspace import Workspace
from finance.storage.projection import ProjectionBuilder
from finance.services.event_sourcing_service import EventSourcingService
from finance.model.events import DuplicateConfirmed


def _find_transaction_by_prefix(
    projection_builder: ProjectionBuilder,
    txid_prefix: str,
    console: Console,
) -> Optional[dict]:
    """Find a transaction by ID prefix (min 8 chars).

    Args:
        projection_builder: Projection builder for querying transactions
        txid_prefix: Transaction ID prefix (minimum 8 characters)
        console: Rich console for error messages

    Returns:
        Transaction dict if found, None otherwise
    """
    if len(txid_prefix) < 8:
        console.print(
            f"[red]Error:[/red] Transaction ID prefix must be at least 8 characters "
            f"(got {len(txid_prefix)})"
        )
        return None

    # Try exact match first
    txn = projection_builder.get_transaction(txid_prefix)
    if txn:
        return txn

    # Try prefix match
    all_txns = projection_builder.get_all_transactions(include_duplicates=True)
    matches = [t for t in all_txns if t["transaction_id"].startswith(txid_prefix)]

    if len(matches) == 0:
        console.print(f"[red]Error:[/red] No transaction found with ID prefix: {txid_prefix}")
        return None
    elif len(matches) > 1:
        console.print(
            f"[red]Error:[/red] Ambiguous transaction ID prefix '{txid_prefix}' "
            f"matches {len(matches)} transactions:"
        )
        for m in matches[:5]:  # Show first 5 matches
            console.print(f"  - {m['transaction_id'][:16]}")
        return None

    return matches[0]


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
        finance mark-duplicate --primary a1b2c3d4 --duplicate e5f6g7h8

        # Confirm and persist
        finance mark-duplicate --primary a1b2c3d4 --duplicate e5f6g7h8 --write
    """
    console = Console()

    if not workspace.ledger_data_dir.exists():
        console.print(f"[red]Error:[/red] Data directory not found: {workspace.ledger_data_dir}")
        return 1

    # Check that projections exist
    if not workspace.projections_path.exists():
        console.print(
            f"[red]Error:[/red] Projections database not found: {workspace.projections_path}"
        )
        console.print("[yellow]Run 'finance rebuild-projections' first.[/yellow]")
        return 1

    # Validate input
    if primary_txid == duplicate_txid:
        console.print("[red]Error:[/red] Primary and duplicate transaction IDs must be different")
        return 1

    # Initialize services
    es_service = EventSourcingService(workspace=workspace)
    projection_builder = ProjectionBuilder(workspace.projections_path)

    # Find transactions
    console.print("[dim]Looking up transactions...[/dim]")
    primary_txn = _find_transaction_by_prefix(projection_builder, primary_txid, console)
    if not primary_txn:
        return 1

    duplicate_txn = _find_transaction_by_prefix(projection_builder, duplicate_txid, console)
    if not duplicate_txn:
        return 1

    # Check if they're already marked as duplicates
    if primary_txn.get("is_duplicate", 0) == 1:
        console.print(
            f"[red]Error:[/red] Primary transaction {primary_txn['transaction_id'][:8]} "
            "is already marked as a duplicate"
        )
        return 1

    if duplicate_txn.get("is_duplicate", 0) == 1:
        txid_short = duplicate_txn['transaction_id'][:8]
        console.print(
            f"[yellow]Warning:[/yellow] Duplicate transaction {txid_short} "
            "is already marked as a duplicate"
        )
        # Allow continuing - user might be reclassifying

    # Validate they could be duplicates (same account, similar amount)
    if primary_txn["account_id"] != duplicate_txn["account_id"]:
        console.print(
            "[yellow]Warning:[/yellow] Transactions are from different accounts:"
        )
        console.print(f"  Primary: {primary_txn['account_id']}")
        console.print(f"  Duplicate: {duplicate_txn['account_id']}")
        if not write:
            console.print("[yellow]Use --write to proceed anyway[/yellow]")

    amount_diff = abs(float(primary_txn["amount"]) - float(duplicate_txn["amount"]))
    if amount_diff > 0.01:  # More than 1 cent difference
        console.print(
            f"[yellow]Warning:[/yellow] Transactions have different amounts "
            f"(difference: {amount_diff:.2f})"
        )
        console.print(f"  Primary: {primary_txn['amount']}")
        console.print(f"  Duplicate: {duplicate_txn['amount']}")
        if not write:
            console.print("[yellow]Use --write to proceed anyway[/yellow]")

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
        dup_id = duplicate_txn['transaction_id'][:8]
        pri_id = primary_txn['transaction_id'][:8]
        console.print(f"  Would mark {dup_id} as duplicate of {pri_id}")
        console.print(f"  Would use description: {canonical_description}")
        console.print()
        console.print("[dim]Use --write to persist changes[/dim]")
        return 0

    # Emit DuplicateConfirmed event
    event = DuplicateConfirmed(
        suggestion_event_id="manual",  # No suggestion event for manual marking
        primary_transaction_id=primary_txn["transaction_id"],
        duplicate_transaction_id=duplicate_txn["transaction_id"],
        canonical_description=canonical_description,
        user_rationale="Manual duplicate marking",
        llm_was_correct=False,  # Not from LLM prediction
    )

    es_service.event_store.append_event(event)

    # Rebuild projections to reflect the change
    console.print("[dim]Rebuilding projections...[/dim]")
    events_processed = projection_builder.rebuild_incremental(es_service.event_store)

    console.print()
    console.print("[green]✓ Duplicate marked successfully[/green]")
    console.print(f"  Primary: {primary_txn['transaction_id'][:8]}")
    dup_id = duplicate_txn['transaction_id'][:8]
    console.print(f"  Duplicate: {dup_id} [dim](hidden from budgets)[/dim]")
    console.print(f"  Description: {canonical_description}")
    console.print(f"  Events processed: {events_processed}")

    return 0
