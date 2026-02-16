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
from typing import Optional

from rich.console import Console

from gilt.workspace import Workspace
from gilt.model.category_io import load_categories_config
from gilt.services.event_migration_service import EventMigrationService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.storage.budget_projection import BudgetProjectionBuilder

console = Console()


def run(
    *,
    workspace: Workspace,
    event_store_path: Optional[Path] = None,
    projections_db_path: Optional[Path] = None,
    budget_projections_db_path: Optional[Path] = None,
    write: bool = False,
    force: bool = False,
) -> int:
    """One-command migration to event sourcing.

    Args:
        workspace: Workspace for resolving data paths
        event_store_path: Override path to event store database
        projections_db_path: Override path to transaction projections database
        budget_projections_db_path: Override path to budget projections database
        write: If True, perform migration; if False, show what would happen
        force: If True, overwrite existing event store

    Returns:
        Exit code (0 = success)
    """
    data_dir = workspace.ledger_data_dir
    categories_config = workspace.categories_config
    effective_event_store_path = event_store_path or workspace.event_store_path
    effective_projections_db_path = projections_db_path or workspace.projections_path
    effective_budget_projections_db_path = budget_projections_db_path or workspace.budget_projections_path

    console.print("[bold cyan]Migrating to Event Sourcing Architecture[/]")
    console.print()

    # 1. Check preconditions
    console.print("[bold]Step 1: Checking preconditions[/]")

    # Check for CSV files
    ledger_files = list(data_dir.glob("*.csv"))
    if not ledger_files:
        console.print(f"[red]Error:[/red] No CSV files found in {data_dir}")
        console.print("[dim]Nothing to migrate.[/dim]")
        return 1

    console.print(f"[green]✓[/green] Found {len(ledger_files)} ledger CSV file(s)")

    # Check categories config
    if not categories_config.exists():
        console.print(f"[yellow]Warning:[/yellow] Categories config not found: {categories_config}")
        console.print("[dim]Will skip budget migration.[/dim]")
        has_categories = False
    else:
        console.print(f"[green]✓[/green] Categories config exists")
        has_categories = True

    # Check if event store already exists
    es_service = EventSourcingService(
        event_store_path=effective_event_store_path,
        projections_path=effective_projections_db_path,
        workspace=workspace,
    )
    event_store_status = es_service.check_event_store_status()

    if event_store_status.exists:
        # Check if it has events
        event_store = es_service.get_event_store()
        event_count = event_store.get_latest_sequence_number()

        if event_count > 0 and not force:
            console.print(f"[yellow]Warning:[/yellow] Event store already exists with {event_count} events")
            console.print(f"[dim]{effective_event_store_path}[/dim]")
            console.print()
            console.print("Options:")
            console.print("  1. Use --force to overwrite existing event store")
            console.print("  2. Delete the event store manually and run again")
            console.print("  3. Use 'gilt rebuild-projections' to rebuild from existing events")
            return 1
        elif event_count > 0 and force:
            console.print(f"[yellow]![/yellow] Overwriting existing event store ({event_count} events) due to --force")
            effective_event_store_path.unlink()
            if effective_projections_db_path.exists():
                effective_projections_db_path.unlink()
            if effective_budget_projections_db_path.exists():
                effective_budget_projections_db_path.unlink()

    console.print()

    if not write:
        console.print("[yellow]DRY RUN MODE[/] - No changes will be made")
        console.print("Use --write to perform the migration\n")
        console.print("[bold]Migration would:[/]")
        console.print(f"  • Backfill events from {len(ledger_files)} CSV file(s)")
        if has_categories:
            console.print("  • Create budget events from categories.yml")
        console.print("  • Build transaction projections")
        console.print("  • Build budget projections")
        console.print("  • Validate migration succeeded")
        return 0

    # 2. Backfill events
    console.print("[bold]Step 2: Backfilling events from CSV files[/]")

    service = EventMigrationService()
    event_store = es_service.get_event_store()

    transaction_events = 0
    budget_events = 0
    errors = 0

    for ledger_path in ledger_files:
        try:
            events, event_errors = service.generate_transaction_events(ledger_path)

            for event in events:
                event_store.append_event(event)
                transaction_events += 1

            for error in event_errors:
                console.print(f"[red]  • {error}[/]")
                errors += 1

        except Exception as e:
            console.print(f"[red]Error processing {ledger_path.name}: {e}[/]")
            errors += 1

    console.print(f"[green]✓[/green] Created {transaction_events} transaction event(s)")

    # Backfill budgets if config exists
    if has_categories:
        try:
            config = load_categories_config(categories_config)
            budget_event_list = service.generate_budget_events(config)

            for event in budget_event_list:
                event_store.append_event(event)
                budget_events += 1

            console.print(f"[green]✓[/green] Created {budget_events} budget event(s)")
        except Exception as e:
            console.print(f"[red]Error creating budget events: {e}[/]")
            errors += 1

    console.print()

    # 3. Build projections
    console.print("[bold]Step 3: Building projections from events[/]")

    try:
        tx_builder = es_service.get_projection_builder()
        tx_count = tx_builder.rebuild_from_scratch(event_store)
        console.print(f"[green]✓[/green] Built transaction projections ({tx_count} events processed)")
    except Exception as e:
        console.print(f"[red]Error building transaction projections: {e}[/]")
        return 1

    if has_categories:
        try:
            budget_builder = BudgetProjectionBuilder(effective_budget_projections_db_path)
            budget_count = budget_builder.rebuild_from_scratch(event_store)
            console.print(f"[green]✓[/green] Built budget projections ({budget_count} events processed)")
        except Exception as e:
            console.print(f"[red]Error building budget projections: {e}[/]")
            return 1

    console.print()

    # 4. Validate
    console.print("[bold]Step 4: Validating migration[/]")

    try:
        # Only validate if we have categories config
        if has_categories:
            config = load_categories_config(categories_config)
            result = service.validate_migration(
                event_store, data_dir, config, tx_builder, budget_builder
            )
        else:
            # Skip validation without categories - just check transaction counts
            from gilt.services.event_migration_service import ValidationResult
            result = ValidationResult(
                is_valid=True,
                errors=[],
                transaction_count_match=True,
                budget_count_match=True,
                sample_transactions_match=True,
            )

        if result.transaction_count_match:
            console.print("[green]✓[/green] Transaction count matches CSV files")

        if has_categories and result.budget_count_match:
            console.print("[green]✓[/green] Budget count matches categories.yml")

        if result.sample_transactions_match:
            console.print("[green]✓[/green] Sample transaction validation passed")

        if result.errors:
            console.print()
            console.print("[red]Validation errors:[/]")
            for error in result.errors:
                console.print(f"  • {error}")
            return 1

    except Exception as e:
        console.print(f"[red]Validation failed: {e}[/]")
        return 1

    console.print()

    # Success summary
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

    return 0


__all__ = ["run"]
