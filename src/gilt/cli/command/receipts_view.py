"""Rich rendering functions for the receipts command."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from gilt.services.receipts_service import CoverageRow, MissingReceiptRow, ReceiptCoverageResult

from ..formatting import fmt_amount_str, fmt_colored_amount


def render_summary(
    result: ReceiptCoverageResult,
    *,
    category: str,
    by_account: bool,
    fy_label: str | None,
    con: Console,
) -> None:
    """Render the coverage summary table."""
    title = f"Receipt Coverage: {category}"
    if fy_label:
        title += f" ({fy_label.upper()})"

    group_col = "account_id" if by_account else "subcategory"

    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("category", style="cyan", no_wrap=True)
    table.add_column(group_col, style="blue")
    table.add_column("total_txns", justify="right")
    table.add_column("with_receipt", justify="right", style="green")
    table.add_column("without_receipt", justify="right", style="yellow")
    table.add_column("coverage_pct", justify="right")
    table.add_column("net_amount", justify="right")

    for row in result.coverage_rows:
        _add_summary_row(table, row, by_account=by_account)

    con.print(table)

    total_txns = sum(r.total_txns for r in result.coverage_rows)
    total_with = sum(r.with_receipt for r in result.coverage_rows)
    total_without = sum(r.without_receipt for r in result.coverage_rows)
    total_net = sum(r.net_amount for r in result.coverage_rows)
    overall_pct = round(total_with / total_txns * 100) if total_txns > 0 else 0

    con.print(
        f"\n[bold]Total:[/] {total_txns} transactions — "
        f"[green]{total_with}[/] with receipt, "
        f"[yellow]{total_without}[/] without  "
        f"([bold]{overall_pct}%[/] coverage)  "
        f"net {fmt_amount_str(total_net)}"
    )


def _add_summary_row(table: Table, row: CoverageRow, *, by_account: bool) -> None:
    """Add one row to the coverage summary table."""
    group_value = row.account_id if by_account else row.subcategory

    pct_str = f"{row.coverage_pct}%" if isinstance(row.coverage_pct, int) else str(row.coverage_pct)
    if isinstance(row.coverage_pct, int):
        if row.coverage_pct == 100:
            pct_str = f"[green bold]{pct_str}[/]"
        elif row.coverage_pct >= 75:
            pct_str = f"[green]{pct_str}[/]"
        elif row.coverage_pct >= 50:
            pct_str = f"[yellow]{pct_str}[/]"
        else:
            pct_str = f"[red]{pct_str}[/]"

    net_str = fmt_colored_amount(row.net_amount)

    table.add_row(
        row.category,
        group_value,
        str(row.total_txns),
        str(row.with_receipt),
        str(row.without_receipt),
        pct_str,
        net_str,
    )


def render_missing(result: ReceiptCoverageResult, con: Console) -> None:
    """Render the list of transactions without receipts."""
    missing = result.missing_rows
    if not missing:
        con.print("[green]✓ All matching transactions have receipts attached.[/green]")
        return

    table = Table(title="Transactions Without Receipts", show_header=True, header_style="bold")
    table.add_column("txid", style="dim", no_wrap=True)
    table.add_column("date")
    table.add_column("description")
    table.add_column("amount", justify="right")
    table.add_column("account_id", style="cyan")

    for row in missing:
        _add_missing_row(table, row)

    con.print(table)
    con.print(f"\n[yellow]{len(missing)} transaction(s) without receipts.[/yellow]")


def _add_missing_row(table: Table, row: MissingReceiptRow) -> None:
    """Add one row to the missing-receipts table."""
    amt_str = fmt_colored_amount(row.amount)

    table.add_row(
        row.transaction_id[:8],
        row.date,
        row.description,
        amt_str,
        row.account_id,
    )
