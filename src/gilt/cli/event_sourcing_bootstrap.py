from __future__ import annotations

from pathlib import Path

from gilt.cli.console import console
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.categorization_persistence_service import CategorizationPersistenceService
from gilt.services.event_sourcing_service import EventSourcingReadyResult, EventSourcingService
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def build_effective_paths(
    workspace: Workspace,
    event_store_path: Path | None,
    projections_db_path: Path | None,
    budget_projections_db_path: Path | None,
) -> tuple[Path, Path, Path]:
    """Resolve effective paths for event store and projections, falling back to workspace defaults."""
    return (
        event_store_path or workspace.event_store_path,
        projections_db_path or workspace.projections_path,
        budget_projections_db_path or workspace.budget_projections_path,
    )


def build_event_sourcing_service(
    workspace: Workspace,
    event_store_path: Path | None = None,
    projections_path: Path | None = None,
) -> EventSourcingService:
    """Construct an EventSourcingService with optional path overrides."""
    return EventSourcingService(
        event_store_path=event_store_path,
        projections_path=projections_path,
        workspace=workspace,
    )


def require_event_sourcing(
    workspace: Workspace,
    *,
    event_store_path: Path | None = None,
    projections_path: Path | None = None,
) -> EventSourcingReadyResult | None:
    """Initialize event sourcing or print error and return None.

    Calls ensure_ready() which auto-rebuilds projections if needed.
    Uses the error message pattern from the duplicates command (most informative).

    Args:
        workspace: Workspace for resolving default paths.
        event_store_path: Override the event store DB path. Defaults to workspace path.
        projections_path: Override the projections DB path. Defaults to workspace path.
    """
    data_dir = workspace.ledger_data_dir
    es_service = build_event_sourcing_service(workspace, event_store_path, projections_path)
    result = es_service.ensure_ready(data_dir=data_dir if data_dir.exists() else None)

    if not result.ready:
        if result.error == "no_event_store":
            console.print(
                f"[yellow]Event store not found, but found {result.csv_files_count} CSV file(s)[/]"
            )
            console.print()
            console.print("[bold]To migrate your existing data to event sourcing:[/]")
            console.print("  gilt migrate-to-events --write")
            console.print()
            console.print(
                "[dim]This will create the event store and projections from your CSV files.[/dim]"
            )
        elif data_dir.exists():
            console.print(f"[red]Error:[/red] No data found in {data_dir}")
            console.print()
            console.print("[bold]To get started:[/]")
            console.print("  1. Export CSV files from your bank")
            console.print("  2. Place them in ingest/ directory")
            console.print("  3. Run: gilt ingest --write")
        else:
            console.print(f"[red]Error:[/red] Data directory not found: {data_dir}")
        return None

    if result.events_processed > 0:
        console.print(
            f"[green]✓[/green] Projections rebuilt ({result.events_processed} events processed)"
        )
        console.print()

    return result


def require_persistence_service(
    ready: EventSourcingReadyResult,
    workspace: Workspace,
) -> CategorizationPersistenceService:
    """Construct a CategorizationPersistenceService from components."""
    return CategorizationPersistenceService(
        event_store=ready.event_store,
        projection_builder=ready.projection_builder,
        ledger_repo=LedgerRepository(workspace.ledger_data_dir),
    )


def require_projections(workspace: Workspace) -> ProjectionBuilder | None:
    """Load projections or print error and return None."""
    if not workspace.projections_path.exists():
        console.print(
            f"[red]Error:[/red] Projections database not found at {workspace.projections_path}\n"
            "[dim]Run 'gilt rebuild-projections' first[/dim]"
        )
        return None
    return ProjectionBuilder(workspace.projections_path)


def load_event_store(workspace: Workspace) -> EventStore | None:
    """Return the event store if it exists, else None (read-only access)."""
    if workspace.event_store_path.exists():
        return build_event_sourcing_service(workspace).get_event_store()
    return None


__all__ = [
    "build_effective_paths",
    "build_event_sourcing_service",
    "require_event_sourcing",
    "require_persistence_service",
    "require_projections",
    "load_event_store",
]
