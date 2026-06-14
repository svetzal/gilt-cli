from __future__ import annotations

"""Display full details of a single transaction by ID prefix."""

import json

from rich.table import Table
from rich.text import Text

from gilt.cli.presentation import build_transaction_table
from gilt.services.transaction_operations_service import TransactionOperationsService
from gilt.workspace import Workspace

from ..console import console
from ..event_sourcing_bootstrap import require_projections
from ..formatting import fmt_amount, fmt_amount_str

_PLACEHOLDER = "—"


def _print_error(msg: str) -> None:
    """Print a formatted error message via the module-level console."""
    console.print(f"[red]Error:[/] {msg}")


def _fmt_value(value: object) -> str:
    """Format a projection field value, using placeholder for None or empty string."""
    if value is None or value == "":
        return _PLACEHOLDER
    return str(value)


def _fmt_bool(value: object) -> str:
    """Format a boolean-ish (0/1 or None) projection field."""
    if value is None:
        return _PLACEHOLDER
    return "Yes" if value else "No"


def _fmt_description_history(raw: str | None) -> str:
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


def _build_detail_table(row: dict) -> Table:
    """Build a Rich key-value table displaying all fields of a single projection row."""
    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_column("Field", style="bold cyan", no_wrap=True, min_width=26)
    table.add_column("Value")

    raw_amount = row.get("amount")
    amount_display: Text | str = (
        fmt_amount(float(raw_amount)) if raw_amount is not None else _PLACEHOLDER
    )

    table.add_row("Transaction ID", _fmt_value(row.get("transaction_id")))
    table.add_row("Date", _fmt_value(row.get("transaction_date")))
    table.add_row("Account", _fmt_value(row.get("account_id")))
    table.add_row("Canonical Description", _fmt_value(row.get("canonical_description")))
    table.add_row("Description History", _fmt_description_history(row.get("description_history")))
    table.add_row("Amount", amount_display)
    table.add_row("Currency", _fmt_value(row.get("currency")))
    table.add_row("Category", _fmt_value(row.get("category")))
    table.add_row("Subcategory", _fmt_value(row.get("subcategory")))
    table.add_row("Counterparty", _fmt_value(row.get("counterparty")))
    table.add_row("Notes", _fmt_value(row.get("notes")))
    table.add_row("Source File", _fmt_value(row.get("source_file")))
    table.add_row("Is Duplicate", _fmt_bool(row.get("is_duplicate")))
    table.add_row("Primary Transaction ID", _fmt_value(row.get("primary_transaction_id")))
    table.add_row("Last Event ID", _fmt_value(row.get("last_event_id")))
    table.add_row("Projection Version", _fmt_value(row.get("projection_version")))
    table.add_row("Vendor", _fmt_value(row.get("vendor")))
    table.add_row("Service", _fmt_value(row.get("service")))
    table.add_row("Invoice Number", _fmt_value(row.get("invoice_number")))
    table.add_row("Tax Amount", _fmt_value(row.get("tax_amount")))
    table.add_row("Tax Type", _fmt_value(row.get("tax_type")))
    table.add_row("Enrichment Currency", _fmt_value(row.get("enrichment_currency")))
    table.add_row("Receipt File", _fmt_value(row.get("receipt_file")))
    table.add_row("Enrichment Source", _fmt_value(row.get("enrichment_source")))
    table.add_row("Source Email", _fmt_value(row.get("source_email")))

    return table


def _display_ambiguous_candidates(transactions: list[dict], ambiguous_ids: list[str]) -> None:
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


def run(*, txid: str, workspace: Workspace) -> int:
    """Display all fields of a single transaction identified by an 8+ character ID prefix.

    Returns:
        0 — transaction found and displayed
        1 — transaction not found / projections missing
        2 — prefix too short or matches multiple transactions
    """
    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return 1

    transactions = projection_builder.get_all_transactions(include_duplicates=True)

    service = TransactionOperationsService()
    normalized = txid.strip().lower()
    result = service.find_projection_by_prefix(normalized, transactions)

    if result.error == "prefix_too_short":
        _print_error(
            f"Transaction ID prefix must be at least 8 characters. Got: {len(txid.strip())}"
        )
        return 2

    if result.error == "not_found":
        _print_error(f"No transaction found matching ID prefix '{txid.strip()}'")
        return 1

    if result.error == "ambiguous":
        console.print(
            f"[yellow]Ambiguous prefix '{txid.strip()}':[/] matches multiple transactions. "
            "Provide a longer prefix to narrow the match."
        )
        _display_ambiguous_candidates(transactions, result.ambiguous_matches or [])
        return 2

    # Single match — display full details
    row = result.transaction or {}
    txn_id_prefix = (row.get("transaction_id") or "")[:8]
    console.print(f"\n[bold]Transaction Detail[/] — [cyan]{txn_id_prefix}[/]\n")
    console.print(_build_detail_table(row))
    return 0


__all__ = ["run"]
