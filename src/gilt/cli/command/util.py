from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

console = Console()


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


def require_projections(workspace: Workspace) -> ProjectionBuilder | None:
    """Load projections or print error and return None."""
    if not workspace.projections_path.exists():
        console.print(
            f"[red]Error:[/red] Projections database not found at {workspace.projections_path}\n"
            "[dim]Run 'gilt rebuild-projections' first[/dim]"
        )
        return None
    return ProjectionBuilder(workspace.projections_path)
