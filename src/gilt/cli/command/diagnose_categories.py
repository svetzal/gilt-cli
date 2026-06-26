from __future__ import annotations

"""
Diagnose category issues by finding categories in transactions that aren't in config.
"""

from gilt.model.category_io import load_categories_config
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.category_diagnostics_service import CategoryDiagnosticsService
from gilt.workspace import Workspace

from ..console import console
from .diagnose_categories_view import display_orphaned_categories


def _load_transactions_from_ledgers(data_dir) -> list[dict]:
    """Load all transactions from ledger CSVs as plain dicts for diagnostic use."""
    return [
        {"category": group.primary.category, "subcategory": group.primary.subcategory}
        for group in LedgerRepository(data_dir).load_all()
    ]


def run(
    *,
    workspace: Workspace,
) -> int:
    """Diagnose category issues by finding categories in transactions not in config.

    Scans all ledger files and reports any categories used in transactions that
    aren't defined in categories.yml. Helps identify orphaned, misspelled, or
    forgotten categories.

    Args:
        workspace: Workspace providing config and data paths

    Returns:
        Exit code (0 if no issues, 1 if orphaned categories found)
    """
    config = workspace.categories_config
    data_dir = workspace.ledger_data_dir

    category_config = load_categories_config(config)
    if not category_config.categories:
        console.print(
            "[yellow]No categories defined in config.[/] "
            "Create config/categories.yml to define valid categories."
        )
        return 0

    transactions = _load_transactions_from_ledgers(data_dir)

    service = CategoryDiagnosticsService(category_config=category_config)
    used = service.collect_used_categories(transactions)

    if not used:
        console.print("[green]No categorized transactions found.[/]")
        return 0

    result = service.find_orphaned_categories(used)

    if not result.orphaned_categories:
        console.print("[green]✓ All categories in transactions are defined in config.[/]")
        return 0

    display_orphaned_categories(result, category_config)
    return 1


__all__ = ["run"]
