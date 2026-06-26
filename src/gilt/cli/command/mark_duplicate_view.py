"""Rich rendering functions for the mark-duplicate command."""

from __future__ import annotations

from rich.table import Table

from ..console import console, print_error


def display_validation_results(validation, write: bool) -> None:
    """Display validation errors and warnings to the console."""
    for error in validation.errors:
        print_error(error)
    for warning in validation.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")
        if not write and ("different account" in warning or "different amount" in warning):
            console.print("[yellow]Use --write to proceed anyway[/yellow]")


def build_comparison_table(primary_txn: dict, duplicate_txn: dict) -> Table:
    """Build a Rich table comparing the two transactions side by side."""
    table = Table(title="Mark Duplicate Transactions", show_header=True, show_lines=True)
    table.add_column("Field", style="cyan")
    table.add_column("Primary (Keep)", style="green")
    table.add_column("Duplicate (Hide)", style="red")
    table.add_row("ID", primary_txn["transaction_id"][:8], duplicate_txn["transaction_id"][:8])
    table.add_row(
        "Date", str(primary_txn["transaction_date"]), str(duplicate_txn["transaction_date"])
    )
    table.add_row("Account", primary_txn["account_id"], duplicate_txn["account_id"])
    table.add_row(
        "Amount", f"{float(primary_txn['amount']):.2f}", f"{float(duplicate_txn['amount']):.2f}"
    )
    table.add_row(
        "Description", primary_txn["canonical_description"], duplicate_txn["canonical_description"]
    )
    return table
