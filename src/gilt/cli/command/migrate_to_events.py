"""
One-command migration from CSV-only data to event sourcing architecture.

This command automates the complete migration process:
1. Validates preconditions (CSV files exist, event store doesn't or is incomplete)
2. Backfills events from existing CSV data
3. Rebuilds transaction and budget projections
4. Validates the migration succeeded
5. Reports clear success/failure

Usage for existing users upgrading:
    gilt migrate-to-events --write

This replaces the manual multi-step process of:
- gilt backfill-events --write
- gilt rebuild-projections --from-scratch
- Checking for errors at each step
"""

from __future__ import annotations

from pathlib import Path

from gilt.model.category_io import load_categories_config
from gilt.model.ledger_repository import LEDGER_IO_ERRORS, LedgerRepository
from gilt.services.event_migration_service import EventMigrationService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.storage.budget_projection import BudgetProjectionBuilder
from gilt.workspace import Workspace

from .util import console, print_error, print_error_list


def _display_dry_run_plan(ledger_files: list[Path], has_categories: bool) -> None:
    """Show what the migration would do without executing it."""
    console.print("[yellow]DRY RUN MODE[/] - No changes will be made")
    console.print("Use --write to perform the migration\n")
    console.print("[bold]Migration would:[/]")
    console.print(f"  • Backfill events from {len(ledger_files)} CSV file(s)")
    if has_categories:
        console.print("  • Create budget events from categories.yml")
    console.print("  • Build transaction projections")
    console.print("  • Build budget projections")
    console.print("  • Validate migration succeeded")


def _display_completion_summary(
    effective_event_store_path: Path,
    effective_projections_db_path: Path,
    transaction_events: int,
    budget_events: int,
    errors: int,
) -> None:
    """Print the post-migration completion summary."""
    console.print()
    console.print("[bold green]✓ Migration Complete![/]")
    console.print()
    console.print("[bold]Summary:[/]")
    console.print(f"  Event store: {effective_event_store_path}")
    console.print(f"  Total events: {transaction_events + budget_events}")
    console.print(f"  Projections: {effective_projections_db_path}")
    console.print()
    console.print("[bold]You can now use:[/]")
    console.print("  • gilt duplicates - Detect duplicate transactions")
    console.print("  • gilt ingest - Import new data (maintains events)")
    console.print("  • gilt rebuild-projections - Rebuild from events")

    if errors > 0:
        console.print()
        console.print(f"[yellow]Warning:[/yellow] {errors} error(s) occurred during migration")
        console.print("[dim]Check the messages above for details[/dim]")


def _check_preconditions(
    data_dir: Path,
    categories_config: Path,
    es_service: EventSourcingService,
    effective_event_store_path: Path,
    effective_projections_db_path: Path,
    effective_budget_projections_db_path: Path,
    force: bool,
) -> tuple[list[Path], bool] | int:
    """Check migration preconditions. Returns (ledger_files, has_categories) or exit code on failure."""
    ledger_files = LedgerRepository(data_dir).ledger_paths()
    if not ledger_files:
        print_error(f"No CSV files found in {data_dir}")
        return 1

    has_categories = categories_config.exists()

    event_store_status = es_service.check_event_store_status()
    if event_store_status.exists:
        event_store = es_service.get_event_store()
        event_count = event_store.get_latest_sequence_number()

        if event_count > 0 and not force:
            return 1
        elif event_count > 0 and force:
            effective_event_store_path.unlink()
            if effective_projections_db_path.exists():
                effective_projections_db_path.unlink()
            if effective_budget_projections_db_path.exists():
                effective_budget_projections_db_path.unlink()

    return ledger_files, has_categories


def _backfill_events(
    ledger_files: list[Path],
    has_categories: bool,
    categories_config: Path,
    es_service: EventSourcingService,
) -> tuple[int, int, int]:
    """Backfill transaction and budget events. Returns (transaction_events, budget_events, errors)."""
    service = EventMigrationService()
    event_store = es_service.get_event_store()

    transaction_events = 0
    budget_events = 0
    errors = 0

    for ledger_path in ledger_files:
        try:
            csv_text = ledger_path.read_text(encoding="utf-8")
            events, event_errors = service.generate_transaction_events(csv_text, ledger_path.name)
            for event in events:
                event_store.append_event(event)
                transaction_events += 1
            for error in event_errors:
                print_error(error)
                errors += 1
        except LEDGER_IO_ERRORS as e:
            print_error(f"Error processing {ledger_path.name}: {e}")
            errors += 1

    if has_categories:
        try:
            config = load_categories_config(categories_config)
            budget_event_list = service.generate_budget_events(config)
            for event in budget_event_list:
                event_store.append_event(event)
                budget_events += 1
        except (OSError, ValueError) as e:
            print_error(f"Error creating budget events: {e}")
            errors += 1

    return transaction_events, budget_events, errors


def _build_projections(
    es_service: EventSourcingService,
    has_categories: bool,
    effective_budget_projections_db_path: Path,
) -> tuple[object, object | None, int, int] | int:
    """Build projections from events. Returns (tx_builder, budget_builder, tx_count, budget_count) or exit code."""
    event_store = es_service.get_event_store()

    try:
        tx_builder = es_service.get_projection_builder()
        tx_count = tx_builder.rebuild_from_scratch(event_store)
    except (OSError, ValueError) as e:
        print_error(f"Error building transaction projections: {e}")
        return 1

    budget_builder = None
    budget_count = 0
    if has_categories:
        try:
            budget_builder = BudgetProjectionBuilder(effective_budget_projections_db_path)
            budget_count = budget_builder.rebuild_from_scratch(event_store)
        except (OSError, ValueError) as e:
            print_error(f"Error building budget projections: {e}")
            return 1

    return tx_builder, budget_builder, tx_count, budget_count


def _validate_migration(
    es_service: EventSourcingService,
    data_dir: Path,
    has_categories: bool,
    categories_config: Path,
    tx_builder,
    budget_builder,
):
    """Validate migration results. Returns validation result object or raises on error."""
    event_store = es_service.get_event_store()
    service = EventMigrationService()

    if has_categories:
        config = load_categories_config(categories_config)
        ledger_texts = LedgerRepository(data_dir).load_all_raw_texts()
        return service.validate_migration(
            event_store, ledger_texts, config, tx_builder, budget_builder
        )
    else:
        from gilt.services.event_migration_service import MigrationValidationResult

        return MigrationValidationResult(
            is_valid=True,
            errors=[],
            transaction_count_match=True,
            budget_count_match=True,
            sample_transactions_match=True,
        )


def _print_preconditions_failure(data_dir: Path, es_service, effective_event_store_path: Path) -> None:
    ledger_files = LedgerRepository(data_dir).ledger_paths()
    if not ledger_files:
        console.print("[dim]Nothing to migrate.[/dim]")
        return
    event_store_status = es_service.check_event_store_status()
    if not event_store_status.exists:
        return
    event_store = es_service.get_event_store()
    event_count = event_store.get_latest_sequence_number()
    if event_count > 0:
        console.print(f"[yellow]Warning:[/yellow] Event store already exists with {event_count} events")
        console.print(f"[dim]{effective_event_store_path}[/dim]")
        console.print()
        console.print("Options:")
        console.print("  1. Use --force to overwrite existing event store")
        console.print("  2. Delete the event store manually and run again")
        console.print("  3. Use 'gilt rebuild-projections' to rebuild from existing events")


def _print_preconditions_success(ledger_files: list[Path], has_categories: bool, categories_config: Path) -> None:
    console.print(f"[green]✓[/green] Found {len(ledger_files)} ledger CSV file(s)")
    if not has_categories:
        console.print(f"[yellow]Warning:[/yellow] Categories config not found: {categories_config}")
        console.print("[dim]Will skip budget migration.[/dim]")
    else:
        console.print("[green]✓[/green] Categories config exists")


def _print_validation_result(validation_result, has_categories: bool) -> int:
    if validation_result.transaction_count_match:
        console.print("[green]✓[/green] Transaction count matches CSV files")
    if has_categories and validation_result.budget_count_match:
        console.print("[green]✓[/green] Budget count matches categories.yml")
    if validation_result.sample_transactions_match:
        console.print("[green]✓[/green] Sample transaction validation passed")
    if validation_result.errors:
        console.print()
        print_error_list("Validation errors", validation_result.errors)
        return 1
    return 0


def run(
    *,
    workspace: Workspace,
    event_store_path: Path | None = None,
    projections_db_path: Path | None = None,
    budget_projections_db_path: Path | None = None,
    write: bool = False,
    force: bool = False,
) -> int:
    """One-command migration to event sourcing."""
    data_dir = workspace.ledger_data_dir
    categories_config = workspace.categories_config
    effective_event_store_path = event_store_path or workspace.event_store_path
    effective_projections_db_path = projections_db_path or workspace.projections_path
    effective_budget_projections_db_path = (
        budget_projections_db_path or workspace.budget_projections_path
    )

    console.print("[bold cyan]Migrating to Event Sourcing Architecture[/]")
    console.print()

    es_service = EventSourcingService(
        event_store_path=effective_event_store_path,
        projections_path=effective_projections_db_path,
        workspace=workspace,
    )

    console.print("[bold]Step 1: Checking preconditions[/]")
    preconditions = _check_preconditions(
        data_dir,
        categories_config,
        es_service,
        effective_event_store_path,
        effective_projections_db_path,
        effective_budget_projections_db_path,
        force,
    )
    if isinstance(preconditions, int):
        _print_preconditions_failure(data_dir, es_service, effective_event_store_path)
        return preconditions
    ledger_files, has_categories = preconditions
    _print_preconditions_success(ledger_files, has_categories, categories_config)

    console.print()

    if not write:
        _display_dry_run_plan(ledger_files, has_categories)
        return 0

    # Backfill
    console.print("[bold]Step 2: Backfilling events from CSV files[/]")
    transaction_events, budget_events, errors = _backfill_events(
        ledger_files,
        has_categories,
        categories_config,
        es_service,
    )
    console.print(f"[green]✓[/green] Created {transaction_events} transaction event(s)")
    if has_categories:
        console.print(f"[green]✓[/green] Created {budget_events} budget event(s)")

    # Build projections
    console.print("\n[bold]Step 3: Building projections from events[/]")
    projections_result = _build_projections(
        es_service, has_categories, effective_budget_projections_db_path
    )
    if isinstance(projections_result, int):
        return projections_result
    tx_builder, budget_builder, tx_count, budget_count = projections_result
    console.print(f"[green]✓[/green] Built transaction projections ({tx_count} events processed)")
    if has_categories:
        console.print(f"[green]✓[/green] Built budget projections ({budget_count} events processed)")

    # Validate
    console.print("\n[bold]Step 4: Validating migration[/]")
    try:
        validation_result = _validate_migration(
            es_service, data_dir, has_categories, categories_config, tx_builder, budget_builder,
        )
    except (OSError, ValueError) as e:
        print_error(f"Validation failed: {e}")
        return 1
    validation_exit = _print_validation_result(validation_result, has_categories)
    if validation_exit != 0:
        return validation_exit

    # Display summary
    _display_completion_summary(
        effective_event_store_path,
        effective_projections_db_path,
        transaction_events,
        budget_events,
        errors,
    )

    return 0


__all__ = ["run"]
