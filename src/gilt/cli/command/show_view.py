"""Rich rendering functions for the show command."""

from __future__ import annotations

import json

from rich.table import Table
from rich.text import Text

from gilt.cli.presentation import build_transaction_table

from ..console import console
from ..formatting import fmt_amount, fmt_amount_str

_PLACEHOLDER = "—"


def fmt_value(value: object) -> str:
    """Format a projection field value, using placeholder for None or empty string."""
    if value is None or value == "":
        return _PLACEHOLDER
    return str(value)


def fmt_bool(value: object) -> str:
    """Format a boolean-ish (0/1 or None) projection field."""
    if value is None:
        return _PLACEHOLDER
    return "Yes" if value else "No"


def fmt_description_history(raw: str | None) -> str:
    """Parse description_history JSON array and format each entry as a bulleted line."""
    if not raw:
        return _PLACEHOLDER
    try:
        history = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return str(raw)
    if not history:
        return _PLACEHOLDER
    return "\n".join(f"  • {item}" for item in history)


def build_detail_table(row: dict) -> Table:
    """Build a Rich key-value table displaying all fields of a single projection row."""
    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_column("Field", style="bold cyan", no_wrap=True, min_width=26)
    table.add_column("Value")

    raw_amount = row.get("amount")
    amount_display: Text | str = (
        fmt_amount(float(raw_amount)) if raw_amount is not None else _PLACEHOLDER
    )

    table.add_row("Transaction ID", fmt_value(row.get("transaction_id")))
    table.add_row("Date", fmt_value(row.get("transaction_date")))
    table.add_row("Account", fmt_value(row.get("account_id")))
    table.add_row("Canonical Description", fmt_value(row.get("canonical_description")))
    table.add_row("Description History", fmt_description_history(row.get("description_history")))
    table.add_row("Amount", amount_display)
    table.add_row("Currency", fmt_value(row.get("currency")))
    table.add_row("Category", fmt_value(row.get("category")))
    table.add_row("Subcategory", fmt_value(row.get("subcategory")))
    table.add_row("Counterparty", fmt_value(row.get("counterparty")))
    table.add_row("Notes", fmt_value(row.get("notes")))
    table.add_row("Source File", fmt_value(row.get("source_file")))
    table.add_row("Is Duplicate", fmt_bool(row.get("is_duplicate")))
    table.add_row("Primary Transaction ID", fmt_value(row.get("primary_transaction_id")))
    table.add_row("Last Event ID", fmt_value(row.get("last_event_id")))
    table.add_row("Projection Version", fmt_value(row.get("projection_version")))
    table.add_row("Vendor", fmt_value(row.get("vendor")))
    table.add_row("Service", fmt_value(row.get("service")))
    table.add_row("Invoice Number", fmt_value(row.get("invoice_number")))
    table.add_row("Tax Amount", fmt_value(row.get("tax_amount")))
    table.add_row("Tax Type", fmt_value(row.get("tax_type")))
    table.add_row("Enrichment Currency", fmt_value(row.get("enrichment_currency")))
    table.add_row("Receipt File", fmt_value(row.get("receipt_file")))
    table.add_row("Enrichment Source", fmt_value(row.get("enrichment_source")))
    table.add_row("Source Email", fmt_value(row.get("source_email")))

    return table


def print_ambiguous_prefix(prefix: str) -> None:
    """Print the message shown when a prefix matches multiple transactions."""
    console.print(
        f"[yellow]Ambiguous prefix '{prefix}':[/] matches multiple transactions. "
        "Provide a longer prefix to narrow the match."
    )


def display_transaction_detail(row: dict) -> None:
    """Print the transaction-detail header and key-value table for a single row."""
    txn_id_prefix = (row.get("transaction_id") or "")[:8]
    console.print(f"\n[bold]Transaction Detail[/] — [cyan]{txn_id_prefix}[/]\n")
    console.print(build_detail_table(row))


def display_ambiguous_candidates(transactions: list[dict], ambiguous_ids: list[str]) -> None:
    """Display a summary table of candidate transactions for an ambiguous prefix."""
    id_set = set(ambiguous_ids)
    candidates = [t for t in transactions if (t.get("transaction_id") or "") in id_set]

    table = build_transaction_table("Ambiguous Prefix — Matching Transactions", [])
    for row in candidates:
        raw_amount = row.get("amount") or 0.0
        table.add_row(
            row.get("account_id") or "",
            (row.get("transaction_id") or "")[:8],
            row.get("transaction_date") or "",
            (row.get("canonical_description") or "")[:40],
            fmt_amount_str(float(raw_amount)),
        )
    console.print(table)
    if len(candidates) > 50:
        console.print(f"[dim]... and {len(candidates) - 50} more[/]")
