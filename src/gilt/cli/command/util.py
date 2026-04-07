from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from gilt.services.categorization_persistence_service import CategorizationPersistenceService
from gilt.services.event_sourcing_service import EventSourcingReadyResult, EventSourcingService
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

console = Console()


def create_transaction_table(title: str, extra_columns: list[tuple[str, dict]]) -> Table:
    """Create a Rich Table with 5 standard transaction columns plus any extra columns.

    The standard columns are: Account (cyan/no_wrap), TxnID (blue/no_wrap),
    Date (white), Description (white), Amount (yellow/right).

    Args:
        title: The table title.
        extra_columns: List of (header, kwargs) pairs appended after the base columns.
            kwargs are keyword arguments for ``Table.add_column`` (e.g. ``{"style": "green"}``).
    """
    table = Table(title=title, show_lines=False)
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("TxnID", style="blue", no_wrap=True)
    table.add_column("Date", style="white")
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    for header, kwargs in extra_columns:
        table.add_column(header, **kwargs)
    return table


def print_transaction_table(
    table: Table,
    total_count: int,
    *,
    display_limit: int = 50,
) -> None:
    """Print a transaction table and an overflow message if total_count exceeds display_limit.

    Args:
        table: The Rich Table to print.
        total_count: The true number of transactions (before any slice was applied).
        display_limit: Maximum rows shown before the overflow message is printed.
    """
    console.print(table)
    if total_count > display_limit:
        console.print(f"[dim]... and {total_count - display_limit} more[/]")


def read_ledger_text(ledger_path: Path) -> str:
    if not ledger_path.exists():
        raise FileNotFoundError(f"Ledger file not found: {ledger_path}")
    return ledger_path.read_text(encoding="utf-8")


def fmt_amount(amt: float) -> Text:
    s = f"{amt:,.2f}"
    if amt < 0:
        return Text(s, style="bold red")
    elif amt > 0:
        return Text(s, style="bold green")
    return Text(s)


def fmt_amount_str(amt: float, *, prefix: str = "$") -> str:
    """Format an amount as a plain string with dollar sign and thousands separator."""
    return f"{prefix}{amt:,.2f}"


def print_dry_run_message(*, detail: str | None = None) -> None:
    """Print the standard dry-run warning. Call when write=False."""
    if detail:
        msg = f"Dry-run: use --write to persist {detail}"
    else:
        msg = "Dry-run: use --write to persist changes"
    console.print(f"[dim]{msg}[/dim]")


def require_event_sourcing(workspace: Workspace) -> EventSourcingReadyResult | None:
    """Initialize event sourcing or print error and return None.

    Calls ensure_ready() which auto-rebuilds projections if needed.
    Uses the error message pattern from the duplicates command (most informative).
    """
    data_dir = workspace.ledger_data_dir
    es_service = EventSourcingService(workspace=workspace)
    result = es_service.ensure_ready(data_dir=data_dir if data_dir.exists() else None)

    if not result.ready:
        if result.error == "no_event_store":
            console.print(
                f"[yellow]Event store not found, but found "
                f"{result.csv_files_count} CSV file(s)[/]"
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
    event_store: EventStore,
    projection_builder: ProjectionBuilder,
    workspace: Workspace,
) -> CategorizationPersistenceService:
    """Construct a CategorizationPersistenceService from components."""
    return CategorizationPersistenceService(
        event_store=event_store,
        projection_builder=projection_builder,
        ledger_data_dir=workspace.ledger_data_dir,
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
