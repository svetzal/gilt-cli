from __future__ import annotations

from datetime import date
from typing import Optional

from rich.table import Table
from rich.text import Text

from gilt.model.account import Transaction
from gilt.storage.projection import ProjectionBuilder
from gilt.ingest import load_accounts_config
from gilt.workspace import Workspace
from .util import console, fmt_amount


def run(
    *,
    account: str,
    year: Optional[int] = None,
    workspace: Workspace,
    limit: Optional[int] = None,
    default_currency: Optional[str] = None,
    include_duplicates: bool = False,
    raw: bool = False,
) -> int:
    """Show year-to-date transactions for a single account as a Rich table.

    Loads transactions from projections database, automatically excluding
    duplicates unless include_duplicates=True.

    Returns an exit code (0 for success, non-zero for error/empty).
    """
    the_year = year or date.today().year
    projections_path = workspace.projections_path

    # Check projections exist
    if not projections_path.exists():
        console.print(f"[red]Error:[/red] Projections database not found: {projections_path}")
        console.print("[yellow]Run 'gilt rebuild-projections' first.[/yellow]")
        return 1

    # Determine account nature from config (default to asset if not found)
    acct_nature = "asset"
    acct_desc_map = {}
    try:
        accounts = load_accounts_config(workspace.accounts_config)
        for a in accounts:
            aid = getattr(a, "account_id", None)
            if aid:
                # Prefer human description if available, else fallback to ID
                acct_desc_map[aid] = getattr(a, "description", None) or aid
            if aid == account:
                # Account.nature is an Enum; get its value string
                acct_nature = getattr(a.nature, "value", str(a.nature))

    except Exception:
        # Best-effort; keep defaults
        pass

    def acct_label(aid: str) -> str:
        return acct_desc_map.get(aid, aid)

    # Load transactions from projections
    projection_builder = ProjectionBuilder(projections_path)
    all_transactions = projection_builder.get_all_transactions(
        include_duplicates=include_duplicates
    )

    # Filter by account and year
    primaries = []
    for row in all_transactions:
        if row["account_id"] != account:
            continue

        # Convert to Transaction object
        txn = Transaction.from_projection_row(row)
        if txn.date.year != the_year:
            continue

        primaries.append(txn)

    primaries.sort(key=lambda t: (t.date, t.transaction_id))

    if limit is not None:
        primaries = primaries[:limit]

    if not primaries:
        console.print(f"[yellow]No transactions for account[/] [bold]{account}[/] in {the_year}.")
        return 0

    # Title with nature indicator
    nature_label = "Asset" if acct_nature == "asset" else "Liability"
    table = Table(title=f"{account} — YTD {the_year} ({nature_label})", show_lines=False)
    table.add_column("Date", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Amount", justify="right")
    table.add_column("Currency", style="magenta", no_wrap=True)
    table.add_column("TxnID8", style="dim", no_wrap=True)
    table.add_column("Notes", style="dim")

    total_amount = 0.0
    credits_amount = 0.0
    debits_amount = 0.0

    for t in primaries:
        amt = t.amount
        total_amount += amt
        if amt > 0:
            credits_amount += amt
        else:
            debits_amount += amt

        # Build notes with category and transfer counterparty when available
        note_parts = []

        # Add category if present
        if t.category:
            cat_display = t.category
            if t.subcategory:
                cat_display += f":{t.subcategory}"
            note_parts.append(f"[yellow]{cat_display}[/yellow]")

        # Add transfer info if present
        try:
            transfer = t.metadata.get("transfer")
            if isinstance(transfer, dict):
                role = transfer.get("role")
                cp_id = transfer.get("counterparty_account_id")
                if cp_id:
                    cp_label = str(cp_id)
                    if role == "debit":
                        tr_note = f"Transfer to {cp_label}"
                    elif role == "credit":
                        tr_note = f"Transfer from {cp_label}"
                    else:
                        tr_note = f"Transfer {cp_label}"
                    note_parts.append(tr_note)
        except Exception:
            # Be resilient if metadata shape is unexpected
            pass

        # Add user notes if present
        if t.notes:
            note_parts.append(t.notes)

        display_notes = " | ".join(note_parts) if note_parts else ""

        # Show vendor name instead of raw bank description when enriched
        display_desc = t.description or ""
        if not raw and t.vendor:
            display_desc = t.vendor

        table.add_row(
            t.date.strftime("%Y-%m-%d"),
            display_desc,
            fmt_amount(amt),
            t.currency or "",
            t.transaction_id[:8],
            display_notes,
        )

    # Totals footer rows (labels depend on account nature)
    label_pos = "Credits" if acct_nature == "asset" else "Charges"
    label_neg = "Debits" if acct_nature == "asset" else "Payments"
    table.add_row("", "", Text(""), "", "", "")
    table.add_row("", Text(label_pos, style="bold"), fmt_amount(credits_amount), "", "", "")
    table.add_row("", Text(label_neg, style="bold"), fmt_amount(debits_amount), "", "", "")
    # Net label varies slightly to hint meaning for liabilities
    net_label = "Net" if acct_nature == "asset" else "Net Change"
    table.add_row("", Text(net_label, style="bold"), fmt_amount(total_amount), "", "", "")

    console.print(table)
    return 0
