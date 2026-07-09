"""Rich rendering functions for the migrate-to-events command."""

from __future__ import annotations

from pathlib import Path

from ..console import console, print_error_list


def print_migration_header() -> None:
    """Print the top-level migration header."""
    console.print("[bold cyan]Migrating to Event Sourcing Architecture[/]")
    console.print()


def print_step_preconditions() -> None:
    """Print the step 1 header."""
    console.print("[bold]Step 1: Checking preconditions[/]")


def print_event_store_exists_warning(event_count: int, path: Path) -> None:
    """Print the warning shown when an event store already exists with events."""
    console.print(
        f"[yellow]Warning:[/yellow] Event store already exists with {event_count} events"
    )
    console.print(f"[dim]{path}[/dim]")
    console.print()
    console.print("Options:")
    console.print("  1. Use --force to overwrite existing event store")
    console.print("  2. Delete the event store manually and run again")
    console.print("  3. Use 'gilt rebuild-projections' to rebuild from existing events")


def display_preconditions_success(
    ledger_files: list[Path], has_categories: bool, categories_config: Path
) -> None:
    """Print the preconditions-passed summary, followed by a trailing blank line."""
    console.print(f"[green]✓[/green] Found {len(ledger_files)} ledger CSV file(s)")
    if not has_categories:
        console.print(f"[yellow]Warning:[/yellow] Categories config not found: {categories_config}")
        console.print("[dim]Will skip budget migration.[/dim]")
    else:
        console.print("[green]✓[/green] Categories config exists")
    console.print()


def display_migration_plan(ledger_files: list[Path], has_categories: bool) -> None:
    """Show what the migration would do without executing it."""
    console.print("[bold]Migration would:[/]")
    console.print(f"  • Backfill events from {len(ledger_files)} CSV file(s)")
    if has_categories:
        console.print("  • Create budget events from categories.yml")
    console.print("  • Build transaction projections")
    console.print("  • Build budget projections")
    console.print("  • Validate migration succeeded")


def print_step_backfill() -> None:
    """Print the step 2 header."""
    console.print("[bold]Step 2: Backfilling events from CSV files[/]")


def print_transaction_events_created(n: int) -> None:
    """Print the count of transaction events created."""
    console.print(f"[green]✓[/green] Created {n} transaction event(s)")


def print_budget_events_created(n: int) -> None:
    """Print the count of budget events created."""
    console.print(f"[green]✓[/green] Created {n} budget event(s)")


def print_step_projections() -> None:
    """Print the step 3 header."""
    console.print("\n[bold]Step 3: Building projections from events[/]")


def print_transaction_projections_built(tx_count: int) -> None:
    """Print confirmation that transaction projections were built."""
    console.print(f"[green]✓[/green] Built transaction projections ({tx_count} events processed)")


def print_budget_projections_built(budget_count: int) -> None:
    """Print confirmation that budget projections were built."""
    console.print(f"[green]✓[/green] Built budget projections ({budget_count} events processed)")


def print_step_validating() -> None:
    """Print the step 4 header."""
    console.print("\n[bold]Step 4: Validating migration[/]")


def display_validation_result(validation_result, has_categories: bool) -> int:
    """Print validation checks; returns 1 if there were errors, else 0."""
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


def display_completion_summary(
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


__all__ = [
    "print_migration_header",
    "print_step_preconditions",
    "print_event_store_exists_warning",
    "display_preconditions_success",
    "display_migration_plan",
    "print_step_backfill",
    "print_transaction_events_created",
    "print_budget_events_created",
    "print_step_projections",
    "print_transaction_projections_built",
    "print_budget_projections_built",
    "print_step_validating",
    "display_validation_result",
    "display_completion_summary",
]
