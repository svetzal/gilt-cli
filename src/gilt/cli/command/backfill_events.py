"""
Backfill events from existing data for event sourcing migration.

This command generates historical events from:
1. Existing transaction ledgers (CSVs) → TransactionImported + TransactionCategorized
2. Budget definitions (categories.yml) → BudgetCreated

⚠️  For most users, use 'gilt migrate-to-events --write' instead.
This command is for advanced use cases and debugging.

Used for Phase 7 migration to event-sourced architecture.

This is the imperative shell - handles I/O, display, and user interaction.
All business logic is in EventMigrationService.
"""

from __future__ import annotations

from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from gilt.model.category_io import load_categories_config
from gilt.services.event_migration_service import EventMigrationService, MigrationStats
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.storage.budget_projection import BudgetProjectionBuilder
from gilt.workspace import Workspace

from .util import console


def run(
    *,
    workspace: Workspace,
    event_store_path: Path | None = None,
    projections_db_path: Path | None = None,
    budget_projections_db_path: Path | None = None,
    dry_run: bool = True,
) -> int:
    """Backfill events from existing ledgers and configuration.

    ⚠️  Most users should use 'gilt migrate-to-events --write' instead.

    Generates historical events from:
    - Transaction ledgers in data_dir
    - Budget definitions in categories_config

    Args:
        workspace: Workspace for resolving data paths
        event_store_path: Override path to event store database
        projections_db_path: Override path to transaction projections database
        budget_projections_db_path: Override path to budget projections database
        dry_run: If True, show what would be created without writing

    Returns:
        Exit code (0 = success)
    """
    data_dir = workspace.ledger_data_dir
    categories_config = workspace.categories_config
    effective_event_store_path = event_store_path or workspace.event_store_path
    effective_projections_db_path = projections_db_path or workspace.projections_path
    effective_budget_projections_db_path = (
        budget_projections_db_path or workspace.budget_projections_path
    )

    console.print("[bold cyan]Event Sourcing Migration - Manual Backfill[/]")
    console.print("[yellow]ℹ Most users should use 'gilt migrate-to-events --write'[/]")
    console.print("Backfilling events from existing data\n")

    if dry_run:
        console.print("[yellow]DRY RUN MODE[/] - No events will be written")
        console.print("Use --write to actually create events\n")

    # Initialize event sourcing service
    es_service = EventSourcingService(
        event_store_path=effective_event_store_path,
        projections_path=effective_projections_db_path,
        workspace=workspace,
    )

    # Initialize service and event store
    service = EventMigrationService()
    event_store = es_service.get_event_store()

    # Track statistics
    stats = MigrationStats(
        transaction_imported=0,
        transaction_categorized=0,
        budget_created=0,
        errors=0,
    )

    # 1. Backfill transaction events from ledgers
    console.print("[bold]Step 1: Backfilling transaction events[/]")
    _backfill_transactions(data_dir, event_store, service, stats, dry_run)

    # 2. Backfill budget events from categories.yml
    console.print("\n[bold]Step 2: Backfilling budget events[/]")
    _backfill_budgets(categories_config, event_store, service, stats, dry_run)

    # Print summary
    console.print("\n[bold cyan]Migration Summary[/]")
    console.print(f"TransactionImported events: {stats.transaction_imported}")
    console.print(f"TransactionCategorized events: {stats.transaction_categorized}")
    console.print(f"BudgetCreated events: {stats.budget_created}")

    if stats.errors > 0:
        console.print(f"[red]Errors: {stats.errors}[/]")

    total_events = stats.transaction_imported + stats.transaction_categorized + stats.budget_created
    console.print(f"\n[bold]Total events: {total_events}[/]")

    if dry_run:
        console.print("\n[yellow]This was a dry run. Use --write to persist events.[/]")
    else:
        console.print("\n[green]✓ Events successfully written to event store[/]")
        console.print(f"Event store: {effective_event_store_path}")

        # Always rebuild projections after writing events
        console.print("\n[bold]Step 3: Rebuilding projections[/]")
        validation_passed = _validate_projections(
            data_dir,
            categories_config,
            event_store,
            service,
            effective_projections_db_path,
            effective_budget_projections_db_path,
        )

        if not validation_passed:
            console.print("[red]✗ Validation failed[/]")
            return 1

    return 0


def _backfill_transactions(
    data_dir: Path,
    event_store,
    service: EventMigrationService,
    stats: MigrationStats,
    dry_run: bool,
) -> None:
    """Backfill transaction events from ledger CSVs.

    Args:
        data_dir: Directory containing ledger files
        event_store: Event store to append events to
        service: Event migration service for business logic
        stats: Statistics object to update
        dry_run: If True, don't actually write events
    """
    ledger_files = sorted(data_dir.glob("*.csv"))

    if not ledger_files:
        console.print("[yellow]No ledger files found[/]")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing ledgers...", total=len(ledger_files))

        for ledger_path in ledger_files:
            try:
                # Use service to generate events
                events, errors = service.generate_transaction_events(ledger_path)

                # Update statistics
                for event in events:
                    if event.event_type == "TransactionImported":
                        stats.transaction_imported += 1
                    elif event.event_type == "TransactionCategorized":
                        stats.transaction_categorized += 1

                    # Write events if not dry run
                    if not dry_run:
                        event_store.append_event(event)

                # Report errors
                for error in errors:
                    console.print(f"[red]{error}[/]")
                    stats.errors += 1

            except Exception as e:
                console.print(f"[red]Error processing {ledger_path.name}: {e}[/]")
                stats.errors += 1

            progress.advance(task)


def _backfill_budgets(
    categories_config: Path,
    event_store,
    service: EventMigrationService,
    stats: MigrationStats,
    dry_run: bool,
) -> None:
    """Backfill budget events from categories.yml.

    Args:
        categories_config: Path to categories.yml
        event_store: Event store to append events to
        service: Event migration service for business logic
        stats: Statistics object to update
        dry_run: If True, don't actually write events
    """
    try:
        config = load_categories_config(categories_config)
    except Exception as e:
        console.print(f"[red]Error loading categories config: {e}[/]")
        stats.errors += 1
        return

    # Use service to generate budget events
    events = service.generate_budget_events(config)

    # Display and write events
    for event in events:
        # Find category for display (event is BudgetCreated with category attribute)
        from gilt.model.events import BudgetCreated

        if isinstance(event, BudgetCreated):
            category = config.find_category(event.category)
            if category and category.budget:
                console.print(
                    f"  {category.name}: ${category.budget.amount}/{category.budget.period.value}"
                )

        stats.budget_created += 1

        if not dry_run:
            event_store.append_event(event)

    if stats.budget_created == 0:
        console.print("[yellow]No budgets found in configuration[/]")


def _validate_projections(
    data_dir: Path,
    categories_config: Path,
    event_store,
    service: EventMigrationService,
    projections_db_path: Path,
    budget_projections_db_path: Path,
) -> bool:
    """Validate that projections rebuilt from events match original data.

    Args:
        data_dir: Directory containing original ledger files
        categories_config: Path to categories.yml
        event_store: Event store with backfilled events
        service: Event migration service for validation logic
        projections_db_path: Path to transaction projections database
        budget_projections_db_path: Path to budget projections database

    Returns:
        True if validation passed, False otherwise
    """
    # Rebuild projections
    console.print("  Rebuilding transaction projections from events...")
    from gilt.storage.projection import ProjectionBuilder

    tx_builder = ProjectionBuilder(projections_db_path)
    tx_count = tx_builder.rebuild_from_scratch(event_store)
    console.print(f"  Processed {tx_count} transaction events")

    console.print("  Rebuilding budget projections from events...")
    budget_builder = BudgetProjectionBuilder(budget_projections_db_path)
    budget_count = budget_builder.rebuild_from_scratch(event_store)
    console.print(f"  Processed {budget_count} budget events")

    # Load category config for validation
    try:
        config = load_categories_config(categories_config)
    except Exception as e:
        console.print(f"[red]Error loading categories config: {e}[/]")
        return False

    # Use service to validate
    console.print("\n  Running validation checks...")
    result = service.validate_migration(event_store, data_dir, config, tx_builder, budget_builder)

    # Display results
    if result.transaction_count_match:
        console.print("  ✓ Transaction count matches")

    if result.budget_count_match:
        console.print("  ✓ Budget count matches")

    if result.sample_transactions_match:
        console.print("  ✓ Sample transaction validation passed")

    # Display errors if any
    if result.errors:
        console.print("\n[red]Validation Errors:[/]")
        for error in result.errors:
            console.print(f"  • {error}")
        return False

    console.print("\n[green]✓ All validations passed[/]")
    return True
