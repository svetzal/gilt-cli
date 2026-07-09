"""Rich rendering functions for the ytd command."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text

from gilt.model.account import Transaction
from gilt.services.transaction_query_service import TransactionQueryService

from ..console import console
from ..formatting import fmt_amount


def print_no_transactions(account: str, the_year: int, compare: bool) -> None:
    """Print the message shown when no transactions match the query."""
    kind = "enriched " if compare else ""
    console.print(
        f"[yellow]No {kind}transactions for account[/] [bold]{account}[/] in {the_year}."
    )


def _build_display_notes(t: Transaction) -> str:
    """Build Rich-markup notes string from category, transfer, and user notes."""
    service = TransactionQueryService()
    plain = service.build_display_notes(t)

    if t.category:
        cat_display = t.category
        if t.subcategory:
            cat_display += f":{t.subcategory}"
        plain_rest = plain[len(cat_display):]
        return f"[yellow]{cat_display}[/yellow]{plain_rest}"

    return plain


def _add_table_row(table: Table, t: Transaction, compare: bool, raw: bool) -> None:
    """Add a single transaction row to the table."""
    display_notes = _build_display_notes(t)

    if compare:
        table.add_row(
            t.date.strftime("%Y-%m-%d"),
            t.description or "",
            t.vendor or "",
            t.service or "",
            fmt_amount(t.amount),
            t.currency or "",
            t.transaction_id[:8],
            display_notes,
        )
    else:
        display_desc = t.description or ""
        if not raw and t.vendor:
            display_desc = f"{t.vendor} - {t.service}" if t.service else t.vendor

        table.add_row(
            t.date.strftime("%Y-%m-%d"),
            display_desc,
            fmt_amount(t.amount),
            t.currency or "",
            t.transaction_id[:8],
            display_notes,
        )


def _add_footer_rows(
    table: Table,
    acct_nature: str,
    compare: bool,
    credits_amount: float,
    debits_amount: float,
    total_amount: float,
) -> None:
    """Add totals footer rows to the table."""
    label_pos = "Credits" if acct_nature == "asset" else "Charges"
    label_neg = "Debits" if acct_nature == "asset" else "Payments"
    net_label = "Net" if acct_nature == "asset" else "Net Change"

    if compare:
        table.add_row("", "", "", "", Text(""), "", "", "")
        table.add_row(
            "", "", Text(label_pos, style="bold"), "", fmt_amount(credits_amount), "", "", ""
        )
        table.add_row(
            "", "", Text(label_neg, style="bold"), "", fmt_amount(debits_amount), "", "", ""
        )
        table.add_row(
            "", "", Text(net_label, style="bold"), "", fmt_amount(total_amount), "", "", ""
        )
    else:
        table.add_row("", "", Text(""), "", "", "")
        table.add_row("", Text(label_pos, style="bold"), fmt_amount(credits_amount), "", "", "")
        table.add_row("", Text(label_neg, style="bold"), fmt_amount(debits_amount), "", "", "")
        table.add_row("", Text(net_label, style="bold"), fmt_amount(total_amount), "", "", "")


def display_ytd_table(
    primaries,
    account: str,
    the_year: int,
    acct_nature: str,
    compare: bool,
    raw: bool,
    query_service,
) -> None:
    """Build and print the YTD transaction table with totals footer."""
    nature_label = "Asset" if acct_nature == "asset" else "Liability"
    title_suffix = " — Enrichment Compare" if compare else ""
    table = Table(
        title=f"{account} — YTD {the_year} ({nature_label}){title_suffix}", show_lines=False
    )
    table.add_column("Date", style="cyan", no_wrap=True)
    if compare:
        table.add_column("Bank Description", style="white")
        table.add_column("Vendor", style="green")
        table.add_column("Service", style="green")
    else:
        table.add_column("Description", style="white")
    table.add_column("Amount", justify="right")
    table.add_column("Currency", style="magenta", no_wrap=True)
    table.add_column("TxnID8", style="dim", no_wrap=True)
    table.add_column("Notes", style="dim")

    totals = query_service.get_totals(primaries)

    for t in primaries:
        _add_table_row(table, t, compare, raw)

    _add_footer_rows(table, acct_nature, compare, totals.credits, totals.debits, totals.net)

    console.print(table)
