from __future__ import annotations

"""
Per-account freshness and coverage dashboard.
"""

import contextlib
from dataclasses import dataclass
from datetime import date

from rich.console import Console
from rich.table import Table

from gilt.workspace import Workspace

from .util import console as _default_console
from .util import require_projections


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


def _passes_fy_filter(txn_date: date, fy_range: tuple[date, date] | None) -> bool:
    """Return True if txn_date is within fy_range (inclusive), or no range is set.

    Uses the same inclusive boundary semantics as TransactionFilter.fy_range.
    """
    if fy_range is None:
        return True
    return fy_range[0] <= txn_date <= fy_range[1]


def _build_account_buckets(rows: list[dict], fy_range: tuple[date, date] | None) -> dict:
    """Accumulate per-account counters from projection rows."""
    accounts: dict[str, dict] = {}

    for row in rows:
        account_id = row.get("account_id") or ""
        if account_id not in accounts:
            accounts[account_id] = {
                "dates": [],
                "total_txns": 0,
                "uncategorized": 0,
                "mojility_txns": 0,
                "mojility_w_receipt": 0,
            }

        bucket = accounts[account_id]
        txn_date_str = row.get("transaction_date") or ""
        txn_date: date | None = None
        with contextlib.suppress(ValueError):
            if txn_date_str:
                txn_date = date.fromisoformat(txn_date_str)
                bucket["dates"].append(txn_date)

        bucket["total_txns"] += 1

        category = row.get("category")
        if not category:
            bucket["uncategorized"] += 1

        if (
            category == "Mojility"
            and txn_date is not None
            and _passes_fy_filter(txn_date, fy_range)
        ):
            bucket["mojility_txns"] += 1
            if bool(row.get("receipt_file")):
                bucket["mojility_w_receipt"] += 1

    return accounts


def _build_status_row(account_id: str, bucket: dict, today: date) -> StatusRow:
    """Convert an account bucket into a StatusRow."""
    dates = bucket["dates"]
    if dates:
        latest_date = max(dates)
        latest_txn: str = str(latest_date)
        days_since: int | str = max(0, (today - latest_date).days)
    else:
        latest_txn = "—"
        days_since = "—"

    moj_txns = bucket["mojility_txns"]
    moj_receipt = bucket["mojility_w_receipt"]
    receipt_pct: int | str = round(moj_receipt / moj_txns * 100) if moj_txns > 0 else "—"

    return StatusRow(
        account_id=account_id,
        latest_txn=latest_txn,
        days_since_latest=days_since,
        total_txns=bucket["total_txns"],
        uncategorized=bucket["uncategorized"],
        mojility_txns=moj_txns,
        mojility_w_receipt=moj_receipt,
        mojility_receipt_pct=receipt_pct,
    )


def _aggregate(
    rows: list[dict],
    fy_range: tuple[date, date] | None,
    today: date,
) -> list[StatusRow]:
    """Aggregate projection rows into per-account StatusRow objects.

    total_txns and uncategorized count all rows (no FY filter).
    mojility_txns and mojility_w_receipt are filtered by fy_range when provided.
    """
    accounts = _build_account_buckets(rows, fy_range)
    return [_build_status_row(aid, accounts[aid], today) for aid in sorted(accounts)]


def _render(
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


def run(
    *,
    fy_range: tuple[date, date] | None = None,
    fy_label: str | None = None,
    stale_threshold: int = 14,
    today: date | None = None,
    workspace: Workspace,
    _console: Console | None = None,
) -> int:
    """Display per-account freshness and coverage dashboard.

    Shows latest transaction date, days since last transaction, total transactions,
    uncategorized count, and Mojility-specific coverage metrics per account.

    Args:
        fy_range: Optional (start, end) date range for Mojility FY filtering
        fy_label: Label string for the fiscal year (e.g. "FY25"), used in column header
        stale_threshold: Days since latest transaction before account is flagged stale
        today: Reference date for staleness calculation (defaults to date.today())
        workspace: Workspace providing data paths
        _console: Optional Rich Console for testing (defaults to module-level console)

    Returns:
        Exit code (0 success, 1 error)
    """
    con = _console if _console is not None else _default_console
    effective_today = today if today is not None else date.today()

    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return 1

    rows = projection_builder.get_all_transactions(include_duplicates=False)

    if not rows:
        con.print("[dim]No transactions found.[/dim]")
        return 0

    status_rows = _aggregate(rows, fy_range, effective_today)
    _render(status_rows, stale_threshold, fy_label, con)
    return 0


__all__ = ["run", "StatusRow"]
