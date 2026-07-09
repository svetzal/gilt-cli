"""Rich rendering functions for the accounts command."""

from __future__ import annotations

from rich.table import Table

from ..console import console


def print_no_accounts() -> None:
    """Print the message shown when no accounts are found."""
    console.print(
        "[yellow]No accounts found.[/] Add entries to config/accounts.yml "
        "or ingest ledgers under data/accounts/."
    )


def display_accounts_table(mapping: dict[str, str]) -> None:
    """Build and print the accounts Rich table."""
    table = Table(title="Available Accounts", show_lines=False)
    table.add_column("Account ID", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")

    for aid in sorted(mapping.keys()):
        table.add_row(aid, mapping[aid])

    console.print(table)
