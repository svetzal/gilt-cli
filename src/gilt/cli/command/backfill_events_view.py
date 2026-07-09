"""Rich rendering functions for the backfill-events command."""

from __future__ import annotations

from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from gilt.model.ledger_repository import LEDGER_IO_ERRORS, LedgerRepository
from gilt.services.event_migration_service import EventMigrationService, MigrationStats

from ..console import console, print_dry_run_message, print_error, print_error_list


def print_migration_header() -> None:
    """Print the manual-backfill banner."""
    console.print("[bold cyan]Event Sourcing Migration - Manual Backfill[/]")
    console.print("[yellow]ℹ Most users should use 'gilt migrate-to-events --write'[/]")
    console.print("Backfilling events from existing data\n")


def print_transaction_step() -> None:
    """Print the Step 1 header."""
    console.print("[bold]Step 1: Backfilling transaction events[/]")


def print_no_ledgers() -> None:
    """Print the no-ledgers-found notice."""
    console.print("[yellow]No ledger files found[/]")


def print_budget_step() -> None:
    """Print the Step 2 header."""
    console.print("\n[bold]Step 2: Backfilling budget events[/]")


def display_budgets(budget_lines: list[str], budget_created: int) -> None:
    """Print each backfilled budget line and a notice when none were found."""
    for line in budget_lines:
        console.print(line)
    if budget_created == 0:
        console.print("[yellow]No budgets found in configuration[/]")


def display_projection_rebuild(tx_count: int, budget_count: int) -> None:
    """Print the Step 3 projection-rebuild progress and event counts."""
    console.print("\n[bold]Step 3: Rebuilding projections[/]")
    console.print("  Rebuilding transaction projections from events...")
    console.print(f"  Processed {tx_count} transaction events")
    console.print("  Rebuilding budget projections from events...")
    console.print(f"  Processed {budget_count} budget events")


def display_validation_checks(result) -> None:
    """Print the validation-check header and each passing check line."""
    console.print("\n  Running validation checks...")
    if result.transaction_count_match:
        console.print("  ✓ Transaction count matches")
    if result.budget_count_match:
        console.print("  ✓ Budget count matches")
    if result.sample_transactions_match:
        console.print("  ✓ Sample transaction validation passed")


def print_validation_errors(errors: list[str]) -> None:
    """Print a blank separator and the list of validation errors."""
    console.print()
    print_error_list("Validation Errors", errors)


def print_all_validations_passed() -> None:
    """Print the all-validations-passed message."""
    console.print("\n[green]✓ All validations passed[/]")


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
        console.print("\n[yellow]This was a dry run.[/]")
        print_dry_run_message()
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
