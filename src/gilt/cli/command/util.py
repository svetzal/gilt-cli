from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

from gilt.model.account import TransactionGroup
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.categorization_persistence_service import CategorizationPersistenceService
from gilt.services.event_sourcing_service import EventSourcingReadyResult, EventSourcingService
from gilt.services.transaction_operations_service import (
    BatchPreview,
    SearchCriteria,
    TransactionOperationsService,
)
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

console = Console()


def print_error(message: str) -> None:
    console.print(f"[red]Error:[/] {message}")


def print_warning(message: str) -> None:
    console.print(f"[yellow]Warning:[/] {message}")


def print_error_list(heading: str, errors: list[str]) -> None:
    console.print(f"[red]{heading}:[/]")
    for error in errors:
        console.print(f"  • {error}")


def filter_uncategorized(rows: list[dict]) -> list[dict]:
    return [row for row in rows if not row.get("category")]


def filter_by_account(rows: list[dict], account: str | None) -> list[dict]:
    if account is None:
        return rows
    return [row for row in rows if row.get("account_id") == account]


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
    es_service = EventSourcingService(
        workspace=workspace,
        event_store_path=event_store_path,
        projections_path=projections_path,
    )
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


def display_transaction_matches(
    title: str,
    extra_columns: list[tuple[str, dict]],
    matches: Sequence,
    row_fn: Callable[[Any], tuple],
    *,
    display_limit: int = 50,
) -> None:
    """Create and print a transaction table for a sequence of matches.

    Args:
        title: Table title passed to ``create_transaction_table``.
        extra_columns: Extra column specs passed to ``create_transaction_table``.
        matches: The full sequence of matches. Only the first ``display_limit`` are rendered.
        row_fn: Callable that accepts a single match item and returns a tuple of column values
            matching (account, txn_id_prefix, date, description, amount, *extra_values).
        display_limit: Maximum rows to render before the overflow message is shown.
    """
    table = create_transaction_table(title, extra_columns)
    for item in matches[:display_limit]:
        table.add_row(*row_fn(item))
    print_transaction_table(table, len(matches), display_limit=display_limit)


def require_projections(workspace: Workspace) -> ProjectionBuilder | None:
    """Load projections or print error and return None."""
    if not workspace.projections_path.exists():
        console.print(
            f"[red]Error:[/red] Projections database not found at {workspace.projections_path}\n"
            "[dim]Run 'gilt rebuild-projections' first[/dim]"
        )
        return None
    return ProjectionBuilder(workspace.projections_path)


def validate_single_vs_batch_mode(
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
) -> bool | None:
    """Validate exactly one of txid/description/desc_prefix/pattern is specified.

    Returns True if single mode (txid), False if batch mode, or None on error.
    Prints an error message when no mode or multiple modes are specified.
    """
    single_mode = bool((txid or "").strip())
    modes_selected = sum(
        [single_mode, description is not None, desc_prefix is not None, pattern is not None]
    )
    if modes_selected != 1:
        print_error(
            "Specify exactly one of --txid, --description, --desc-prefix, or --pattern"
        )
        return None
    return single_mode


def resolve_id_prefix(
    service: TransactionOperationsService,
    prefix: str,
    groups: list[TransactionGroup],
) -> list[TransactionGroup] | str:
    """Find transactions by ID prefix with validation and formatted error messages.

    Validates the prefix is at least 8 characters, calls find_by_id_prefix,
    and returns either the matched groups or an error string describing the problem.

    Args:
        service: Service used to perform the lookup.
        prefix: Transaction ID prefix to look up.
        groups: Transaction groups to search within.

    Returns:
        A list of matching TransactionGroup objects on success, or a non-empty
        error string describing the problem (not_found or ambiguous).
    """
    normalized = prefix.strip().lower()
    if len(normalized) < 8:
        return f"Transaction ID prefix must be at least 8 characters. Got: {len(normalized)}"

    result = service.find_by_id_prefix(normalized, groups)

    if result.type == "not_found":
        return f"No transaction found matching ID prefix '{normalized}'"

    if result.type == "ambiguous":
        sample = []
        for g in (result.matches or [])[:5]:
            t = g.primary
            sample.append(
                f"{t.date} id={t.transaction_id[:8]} amt={t.amount} desc='{(t.description or '').strip()}'"
            )
        detail = (" Examples: " + "; ".join(sample)) if sample else ""
        return (
            f"Ambiguous prefix '{normalized}': matches {len(result.matches or [])} transactions."
            + detail
        )

    return [result.transaction] if result.transaction else []


def search_by_criteria(
    service: TransactionOperationsService,
    criteria: SearchCriteria,
    groups: list[TransactionGroup],
    pattern: str | None,
) -> BatchPreview | None:
    """Search for transactions by criteria, printing warnings and errors as needed.

    Calls find_by_criteria on the service. If the pattern is invalid, prints an error
    and returns None. If sign-insensitive matching was used, prints a note.

    Args:
        service: Service used to perform the search.
        criteria: Search criteria (description, desc_prefix, pattern, amount).
        groups: Transaction groups to search within.
        pattern: The raw pattern string (used only in the error message).

    Returns:
        A BatchPreview on success, or None if the pattern was invalid.
    """
    preview = service.find_by_criteria(criteria, groups)

    if preview.invalid_pattern:
        print_error(f"Invalid regex pattern: {pattern}")
        return None

    if preview.used_sign_insensitive:
        console.print(
            "[yellow]Note:[/] matched by absolute amount "
            "since no signed matches were found. "
            "Ledger stores debits as negative amounts."
        )

    return preview
