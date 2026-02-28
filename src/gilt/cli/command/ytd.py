from __future__ import annotations

from datetime import date

from rich.table import Table
from rich.text import Text

from gilt.ingest import load_accounts_config
from gilt.model.account import Transaction
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

from .util import console, fmt_amount


def _load_and_filter_transactions(
    workspace: Workspace,
    account: str,
    the_year: int,
    include_duplicates: bool,
    limit: int | None,
    compare: bool,
) -> list[Transaction] | int:
    """Load, filter, and sort transactions. Returns list or exit code on error."""
    projections_path = workspace.projections_path
    if not projections_path.exists():
        console.print(f"[red]Error:[/red] Projections database not found: {projections_path}")
        console.print("[yellow]Run 'gilt rebuild-projections' first.[/yellow]")
        return 1

    projection_builder = ProjectionBuilder(projections_path)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=include_duplicates)

    primaries = []
    for row in all_transactions:
        if row["account_id"] != account:
            continue
        txn = Transaction.from_projection_row(row)
        if txn.date.year != the_year:
            continue
        primaries.append(txn)

    primaries.sort(key=lambda t: (t.date, t.transaction_id))

    if limit is not None:
        primaries = primaries[:limit]

    if compare:
        primaries = [t for t in primaries if t.vendor]

    return primaries


def _build_display_notes(t: Transaction) -> str:
    """Build combined notes string from category, transfer, and user notes."""
    note_parts = []

    if t.category:
        cat_display = t.category
        if t.subcategory:
            cat_display += f":{t.subcategory}"
        note_parts.append(f"[yellow]{cat_display}[/yellow]")

    try:
        transfer = t.metadata.get("transfer")
        if isinstance(transfer, dict):
            role = transfer.get("role")
            cp_id = transfer.get("counterparty_account_id")
            if cp_id:
                cp_label = str(cp_id)
                if role == "debit":
                    note_parts.append(f"Transfer to {cp_label}")
                elif role == "credit":
                    note_parts.append(f"Transfer from {cp_label}")
                else:
                    note_parts.append(f"Transfer {cp_label}")
    except Exception:
        pass

    if t.notes:
        note_parts.append(t.notes)

    return " | ".join(note_parts) if note_parts else ""


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
    table: Table, acct_nature: str, compare: bool,
    credits_amount: float, debits_amount: float, total_amount: float,
) -> None:
    """Add totals footer rows to the table."""
    label_pos = "Credits" if acct_nature == "asset" else "Charges"
    label_neg = "Debits" if acct_nature == "asset" else "Payments"
    net_label = "Net" if acct_nature == "asset" else "Net Change"

    if compare:
        table.add_row("", "", "", "", Text(""), "", "", "")
        table.add_row("", "", Text(label_pos, style="bold"), "", fmt_amount(credits_amount), "", "", "")
        table.add_row("", "", Text(label_neg, style="bold"), "", fmt_amount(debits_amount), "", "", "")
        table.add_row("", "", Text(net_label, style="bold"), "", fmt_amount(total_amount), "", "", "")
    else:
        table.add_row("", "", Text(""), "", "", "")
        table.add_row("", Text(label_pos, style="bold"), fmt_amount(credits_amount), "", "", "")
        table.add_row("", Text(label_neg, style="bold"), fmt_amount(debits_amount), "", "", "")
        table.add_row("", Text(net_label, style="bold"), fmt_amount(total_amount), "", "", "")


def run(
    *,
    account: str,
    year: int | None = None,
    workspace: Workspace,
    limit: int | None = None,
    default_currency: str | None = None,
    include_duplicates: bool = False,
    raw: bool = False,
    compare: bool = False,
) -> int:
    """Show year-to-date transactions for a single account as a Rich table."""
    the_year = year or date.today().year

    acct_nature = "asset"
    try:
        accounts = load_accounts_config(workspace.accounts_config)
        for a in accounts:
            aid = getattr(a, "account_id", None)
            if aid == account:
                acct_nature = getattr(a.nature, "value", str(a.nature))
    except Exception:
        pass

    result = _load_and_filter_transactions(workspace, account, the_year, include_duplicates, limit, compare)
    if isinstance(result, int):
        return result
    primaries = result

    if not primaries:
        kind = "enriched " if compare else ""
        console.print(f"[yellow]No {kind}transactions for account[/] [bold]{account}[/] in {the_year}.")
        return 0

    nature_label = "Asset" if acct_nature == "asset" else "Liability"
    title_suffix = " — Enrichment Compare" if compare else ""
    table = Table(title=f"{account} — YTD {the_year} ({nature_label}){title_suffix}", show_lines=False)
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

    total_amount = 0.0
    credits_amount = 0.0
    debits_amount = 0.0

    for t in primaries:
        total_amount += t.amount
        if t.amount > 0:
            credits_amount += t.amount
        else:
            debits_amount += t.amount
        _add_table_row(table, t, compare, raw)

    _add_footer_rows(table, acct_nature, compare, credits_amount, debits_amount, total_amount)

    console.print(table)
    return 0
