"""Rich rendering functions for the backfill-events command."""

from __future__ import annotations

from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from gilt.model.ledger_repository import LEDGER_IO_ERRORS, LedgerRepository
from gilt.services.event_migration_service import EventMigrationService, MigrationStats

from ..console import console, print_error


def display_summary(
    stats: MigrationStats, dry_run: bool, effective_event_store_path: Path
) -> None:
    """Print the migration summary and dry-run/completion message."""
    console.print("\n[bold cyan]Migration Summary[/]")
    console.print(f"TransactionImported events: {stats.transaction_imported}")
    console.print(f"TransactionCategorized events: {stats.transaction_categorized}")
    console.print(f"BudgetCreated events: {stats.budget_created}")

    if stats.errors > 0:
        print_error(f"Errors: {stats.errors}")

    total_events = stats.transaction_imported + stats.transaction_categorized + stats.budget_created
    console.print(f"\n[bold]Total events: {total_events}[/]")

    if dry_run:
        console.print("\n[yellow]This was a dry run. Use --write to persist events.[/]")
    else:
        console.print("\n[green]✓ Events successfully written to event store[/]")
        console.print(f"Event store: {effective_event_store_path}")


def backfill_transactions_with_progress(
    data_dir: Path,
    event_store,
    service: EventMigrationService,
    stats: MigrationStats,
    dry_run: bool,
) -> int:
    """Backfill transaction events from ledger CSVs with a progress spinner. Returns ledger file count."""
    ledger_files = LedgerRepository(data_dir).ledger_paths()

    if not ledger_files:
        return 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing ledgers...", total=len(ledger_files))

        for ledger_path in ledger_files:
            try:
                csv_text = ledger_path.read_text(encoding="utf-8")
                events, errors = service.build_transaction_events(csv_text, ledger_path.name)

                for event in events:
                    if event.event_type == "TransactionImported":
                        stats.transaction_imported += 1
                    elif event.event_type == "TransactionCategorized":
                        stats.transaction_categorized += 1

                    if not dry_run:
                        event_store.append_event(event)

                for error in errors:
                    print_error(error)
                    stats.errors += 1

            except LEDGER_IO_ERRORS as e:
                print_error(f"Error processing {ledger_path.name}: {e}")
                stats.errors += 1

            progress.advance(task)

    return len(ledger_files)
