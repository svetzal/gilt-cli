"""Rich rendering functions for the status command."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.table import Table


@dataclass
class StatusRow:
    account_id: str
    latest_txn: str  # "YYYY-MM-DD" or "—"
    days_since_latest: int | str  # int or "—"
    total_txns: int
    uncategorized: int
    mojility_txns: int
    mojility_w_receipt: int
    mojility_receipt_pct: int | str  # int or "—"


def render(
    status_rows: list[StatusRow],
    stale_threshold: int,
    fy_label: str | None,
    console: Console,
) -> None:
    """Render the status dashboard as a Rich table."""
    moj_header = "mojility_txns"
    if fy_label:
        moj_header = f"mojility_txns ({fy_label.upper()})"

    table = Table(title="Account Status", show_header=True, header_style="bold")
    table.add_column("account_id", style="cyan")
    table.add_column("latest_txn")
    table.add_column("days_since", justify="right")
    table.add_column("total_txns", justify="right")
    table.add_column("uncategorized", justify="right")
    table.add_column(moj_header, justify="right")
    table.add_column("mojility_w_receipt", justify="right")
    table.add_column("mojility_receipt_pct", justify="right")

    for row in status_rows:
        days = row.days_since_latest
        stale = isinstance(days, int) and days > stale_threshold

        account_cell = row.account_id
        latest_cell = str(row.latest_txn)
        days_cell = str(days)

        if stale:
            account_cell = f"[red]⚠ {account_cell}[/red]"
            latest_cell = f"[red]{latest_cell}[/red]"
            days_cell = f"[red]{days_cell}[/red]"

        table.add_row(
            account_cell,
            latest_cell,
            days_cell,
            str(row.total_txns),
            str(row.uncategorized),
            str(row.mojility_txns),
            str(row.mojility_w_receipt),
            str(row.mojility_receipt_pct),
        )

    console.print(table)
