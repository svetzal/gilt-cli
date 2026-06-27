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

from gilt.workspace import Workspace

from ..console import console, print_error
from ..event_sourcing_bootstrap import build_event_sourcing_service
from ._errors import CommandAbort
from .rebuild_projections_view import display_rebuild_summary


def run(
    workspace: Workspace,
    from_scratch: bool = False,
    incremental: bool = False,
    events_db: Path | None = None,
    projections_db: Path | None = None,
) -> int:
    """Rebuild transaction projections from event store.

    By default, applies only new events since last rebuild (incremental mode).
    Use --from-scratch to rebuild everything from all events.

    This demonstrates a key benefit of event sourcing: the current state
    can be reconstructed at any time by replaying the immutable event log.
    """
    es_service = build_event_sourcing_service(workspace, events_db, projections_db)

    event_store_status = es_service.check_event_store_status()
    if not event_store_status.exists:
        print_error(f"Event store not found: {event_store_status.path}")
        console.print("[dim]Run 'gilt ingest --write' first to create events.[/dim]")
        raise CommandAbort(1)

    event_store = es_service.get_event_store()
    projection_builder = es_service.get_projection_builder()

    mode = "from-scratch" if from_scratch else "incremental"

    console.print(f"[bold]Rebuilding projections ({mode} mode)[/bold]")
    console.print(f"Events DB: {es_service.event_store_path}")
    console.print(f"Projections DB: {es_service.projections_path}")
    console.print()

    all_events = event_store.get_all_events()
    total_events = len(all_events)

    if total_events == 0:
        console.print("[yellow]Warning:[/yellow] Event store is empty")
        return 0

    return _rebuild_and_report(from_scratch, projection_builder, event_store, total_events)


def _rebuild_and_report(
    from_scratch: bool, projection_builder, event_store, total_events: int
) -> int:
    """Rebuild projections (from scratch or incremental) and display summary."""
    try:
        if from_scratch:
            console.print(f"[dim]Processing {total_events} events...[/dim]")
            processed = projection_builder.build_from_scratch(event_store)
        else:
            processed = projection_builder.build_incremental(event_store)
            if processed == 0:
                console.print("[green]✓[/green] Projections already up to date")
                return 0

        console.print(f"[green]✓[/green] Processed {processed} events")

        transactions = projection_builder.get_all_transactions(include_duplicates=False)
        duplicates = projection_builder.get_all_transactions(include_duplicates=True)
        display_rebuild_summary(transactions, duplicates)

        return 0

    except (OSError, ValueError) as e:
        print_error(f"Error rebuilding projections: {e}")
        raise CommandAbort(1) from None


__all__ = ["run"]
