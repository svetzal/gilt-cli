"""Rich rendering functions for the rebuild-projections command."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from ..console import console


def print_event_store_missing_hint() -> None:
    """Show the hint to run ingest when the event store is missing."""
    console.print("[dim]Run 'gilt ingest --write' first to create events.[/dim]")


def display_rebuild_header(mode: str, events_path: Path, projections_path: Path) -> None:
    """Show the rebuild header with mode and database paths."""
    console.print(f"[bold]Rebuilding projections ({mode} mode)[/bold]")
    console.print(f"Events DB: {events_path}")
    console.print(f"Projections DB: {projections_path}")
    console.print()


def print_empty_event_store_warning() -> None:
    """Warn that the event store contains no events."""
    console.print("[yellow]Warning:[/yellow] Event store is empty")


def print_processing_events(total_events: int) -> None:
    """Show how many events are being processed in a from-scratch rebuild."""
    console.print(f"[dim]Processing {total_events} events...[/dim]")


def print_already_up_to_date() -> None:
    """Report that projections are already current (incremental no-op)."""
    console.print("[green]✓[/green] Projections already up to date")


def print_processed_events(processed: int) -> None:
    """Report the number of events processed during the rebuild."""
    console.print(f"[green]✓[/green] Processed {processed} events")


def display_rebuild_summary(
    transactions: list,
    duplicates: list,
) -> None:
    """Display the rebuild summary including account breakdown and enrichment stats."""
    num_duplicates = len(duplicates) - len(transactions)

    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Total transactions: {len(transactions)}")
    if num_duplicates > 0:
        console.print(f"  Duplicates detected: {num_duplicates}")

    accounts = {}
    for txn in transactions:
        account_id = txn["account_id"]
        accounts[account_id] = accounts.get(account_id, 0) + 1

    if accounts:
        console.print()
        table = Table(title="Transactions by Account")
        table.add_column("Account", style="cyan")
        table.add_column("Count", justify="right", style="green")

        for account_id in sorted(accounts.keys()):
            table.add_row(account_id, str(accounts[account_id]))

        console.print(table)

    evolved_count = sum(
        1
        for txn in transactions
        if txn.get("description_history") and len(eval(txn["description_history"])) > 1
    )

    if evolved_count > 0:
        console.print()
        console.print(f"[dim]ℹ {evolved_count} transactions have evolved descriptions[/dim]")

    enriched_count = sum(1 for txn in transactions if txn.get("vendor"))
    if enriched_count > 0:
        console.print(f"[dim]ℹ {enriched_count} transactions enriched with receipt data[/dim]")
