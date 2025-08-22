from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from rich.table import Table
from rich.text import Text

from finance.model.ledger_io import load_ledger_csv
from finance.ingest import load_accounts_config
from .util import console, fmt_amount, read_ledger_text


def run(
    *,
    account: str,
    year: Optional[int] = None,
    data_dir: Path = Path("data/accounts"),
    limit: Optional[int] = None,
    default_currency: Optional[str] = None,
) -> int:
    """Show year-to-date transactions for a single account as a Rich table.

    Returns an exit code (0 for success, non-zero for error/empty).
    """
    the_year = year or date.today().year
    ledger_path = data_dir / f"{account}.csv"

    # Determine account nature from config (default to asset if not found)
    acct_nature = "asset"
    acct_desc_map = {}
    try:
        accounts = load_accounts_config(Path("config/accounts.yml"))
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

    try:
        csv_text = read_ledger_text(ledger_path)
    except FileNotFoundError:
        console.print(f"[yellow]No ledger found for account[/] [bold]{account}[/] at {ledger_path}")
        return 1

    groups = load_ledger_csv(csv_text, default_currency=default_currency)

    primaries = [
        g.primary
        for g in groups
        if getattr(g.primary, "account_id", None) == account and g.primary.date.year == the_year
    ]
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
        amt = float(t.amount)
        total_amount += amt
        if amt > 0:
            credits_amount += amt
        else:
            debits_amount += amt

        # Build notes with transfer counterparty when available
        display_notes = t.notes or ""
        try:
            transfer = (t.metadata or {}).get("transfer") if hasattr(t, "metadata") else None
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
                    display_notes = tr_note if not display_notes else f"{tr_note}, {display_notes}"
        except Exception:
            # Be resilient if metadata shape is unexpected
            pass

        table.add_row(
            t.date.strftime("%Y-%m-%d"),
            t.description or "",
            fmt_amount(amt),
            t.currency or "",
            (t.transaction_id or "")[:8],
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
