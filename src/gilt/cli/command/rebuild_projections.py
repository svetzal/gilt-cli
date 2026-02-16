"""
CLI command to rebuild transaction projections from event store.

This command demonstrates the power of event sourcing: we can rebuild
the entire current state from the immutable event log at any time.

Usage:
    gilt rebuild-projections [OPTIONS]

Options:
    --from-scratch    Delete existing projections and rebuild from all events
    --incremental     Only apply new events since last rebuild (default)
    --events-db PATH  Path to events database (default: data/events.db)
    --projections-db PATH  Path to projections database (default: data/projections.db)
"""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from gilt.workspace import Workspace
from gilt.services.event_sourcing_service import EventSourcingService

console = Console()


def run(
    workspace: Workspace,
    from_scratch: bool = False,
    incremental: bool = False,
    events_db: Optional[Path] = None,
    projections_db: Optional[Path] = None,
) -> int:
    """Rebuild transaction projections from event store.

    By default, applies only new events since last rebuild (incremental mode).
    Use --from-scratch to rebuild everything from all events.

    This demonstrates a key benefit of event sourcing: the current state
    can be reconstructed at any time by replaying the immutable event log.
    """
    # Initialize event sourcing service with optional custom paths
    es_service = EventSourcingService(
        event_store_path=events_db,
        projections_path=projections_db,
        workspace=workspace,
    )

    # Check if event store exists
    event_store_status = es_service.check_event_store_status()
    if not event_store_status.exists:
        console.print(f"[red]Error:[/red] Event store not found: {event_store_status.path}")
        console.print("[dim]Run 'gilt ingest --write' first to create events.[/dim]")
        return 1

    # Get instances
    event_store = es_service.get_event_store()
    projection_builder = es_service.get_projection_builder()

    # Determine mode (default to incremental unless --from-scratch specified)
    mode = "from-scratch" if from_scratch else "incremental"

    console.print(f"[bold]Rebuilding projections ({mode} mode)[/bold]")
    console.print(f"Events DB: {es_service.event_store_path}")
    console.print(f"Projections DB: {es_service.projections_path}")
    console.print()

    # Get event counts
    all_events = event_store.get_all_events()
    total_events = len(all_events)

    if total_events == 0:
        console.print("[yellow]Warning:[/yellow] Event store is empty")
        return 0

    # Rebuild projections
    try:
        if from_scratch:
            console.print(f"[dim]Processing {total_events} events...[/dim]")
            processed = projection_builder.rebuild_from_scratch(event_store)
        else:
            processed = projection_builder.rebuild_incremental(event_store)
            if processed == 0:
                console.print("[green]✓[/green] Projections already up to date")
                return 0

        console.print(f"[green]✓[/green] Processed {processed} events")

        # Display summary
        transactions = projection_builder.get_all_transactions(include_duplicates=False)
        duplicates = projection_builder.get_all_transactions(include_duplicates=True)
        num_duplicates = len(duplicates) - len(transactions)

        console.print()
        console.print("[bold]Summary:[/bold]")
        console.print(f"  Total transactions: {len(transactions)}")
        if num_duplicates > 0:
            console.print(f"  Duplicates detected: {num_duplicates}")

        # Show transaction breakdown by account
        accounts = {}
        for txn in transactions:
            account_id = txn["account_id"]
            accounts[account_id] = accounts.get(account_id, 0) + 1

        if accounts:
            console.print()
            table = Table(title="Transactions by Account")
            table.add_column("Account", style="cyan")
            table.add_column("Count", justify="right", style="green")

            for account_id in sorted(accounts.keys()):
                table.add_row(account_id, str(accounts[account_id]))

            console.print(table)

        # Show description evolution examples
        evolved_count = sum(
            1
            for txn in transactions
            if txn.get("description_history") and len(eval(txn["description_history"])) > 1
        )

        if evolved_count > 0:
            console.print()
            console.print(f"[dim]ℹ {evolved_count} transactions have evolved descriptions[/dim]")

        return 0

    except Exception as e:
        console.print(f"[red]Error rebuilding projections:[/red] {e}")
        return 1


__all__ = ["run"]
