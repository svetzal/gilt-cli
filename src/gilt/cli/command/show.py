from __future__ import annotations

"""Display full details of a single transaction by ID prefix."""

from gilt.services.transaction_operations_service import TransactionOperationsService
from gilt.workspace import Workspace

from ..console import print_error
from ..event_sourcing_bootstrap import require_projections
from .show_view import (
    display_ambiguous_candidates,
    display_transaction_detail,
    print_ambiguous_prefix,
)


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
        print_error(
            f"Transaction ID prefix must be at least 8 characters. Got: {len(txid.strip())}"
        )
        return 2

    if result.error == "not_found":
        print_error(f"No transaction found matching ID prefix '{txid.strip()}'")
        return 1

    if result.error == "ambiguous":
        print_ambiguous_prefix(txid.strip())
        display_ambiguous_candidates(transactions, result.ambiguous_matches or [])
        return 2

    row = result.transaction or {}
    display_transaction_detail(row)
    return 0


__all__ = ["run"]
