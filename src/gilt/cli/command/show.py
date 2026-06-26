from __future__ import annotations

"""Display full details of a single transaction by ID prefix."""

from gilt.services.transaction_operations_service import TransactionOperationsService
from gilt.workspace import Workspace

from ..console import console
from ..event_sourcing_bootstrap import require_projections
from .show_view import build_detail_table, display_ambiguous_candidates


def _print_error(msg: str) -> None:
    """Print a formatted error message via the module-level console."""
    console.print(f"[red]Error:[/] {msg}")


def run(*, txid: str, workspace: Workspace) -> int:
    """Display all fields of a single transaction identified by an 8+ character ID prefix.

    Returns:
        0 — transaction found and displayed
        1 — transaction not found / projections missing
        2 — prefix too short or matches multiple transactions
    """
    projection_builder = require_projections(workspace)
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
        display_ambiguous_candidates(transactions, result.ambiguous_matches or [])
        return 2

    row = result.transaction or {}
    txn_id_prefix = (row.get("transaction_id") or "")[:8]
    console.print(f"\n[bold]Transaction Detail[/] — [cyan]{txn_id_prefix}[/]\n")
    console.print(build_detail_table(row))
    return 0


__all__ = ["run"]
