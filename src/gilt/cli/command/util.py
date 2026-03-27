from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.text import Text

from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

console = Console()


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
