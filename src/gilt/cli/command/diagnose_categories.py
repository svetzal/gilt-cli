from __future__ import annotations

"""
Diagnose category issues by finding categories in transactions that aren't in config.
"""

from rich.table import Table

from gilt.model.category_io import load_categories_config
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.category_diagnostics_service import CategoryDiagnosticsService
from gilt.workspace import Workspace

from .util import console


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

    # Load config
    category_config = load_categories_config(config)
    if not category_config.categories:
        console.print(
            "[yellow]No categories defined in config.[/] "
            "Create config/categories.yml to define valid categories."
        )
        return 0

    # Load transactions from ledger files
    transactions = _load_transactions_from_ledgers(data_dir)

    # Use service for diagnostics
    service = CategoryDiagnosticsService(category_config=category_config)
    used = service.collect_used_categories(transactions)

    if not used:
        console.print("[green]No categorized transactions found.[/]")
        return 0

    result = service.find_orphaned_categories(used)

    if not result.orphaned_categories:
        console.print("[green]✓ All categories in transactions are defined in config.[/]")
        return 0

    # Display orphaned categories
    console.print(
        f"[yellow]Found {len(result.orphaned_categories)} category/subcategory combination(s) "
        f"in transactions that are not defined in categories.yml:[/]\n"
    )

    table = Table(title="Orphaned Categories", show_lines=False)
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Subcategory", style="blue")
    table.add_column("Transaction Count", style="yellow", justify="right")
    table.add_column("Suggested Action", style="white")

    # Build defined set once for suggestions
    defined_categories = {(cat.name, None) for cat in category_config.categories}
    for cat in category_config.categories:
        for subcat in cat.subcategories:
            defined_categories.add((cat.name, subcat.name))

    sorted_orphaned = sorted(
        result.orphaned_categories, key=lambda o: (o.category, o.subcategory or "")
    )

    for orphan in sorted_orphaned:
        cat = orphan.category
        subcat = orphan.subcategory
        cat_only_defined = (cat, None) in defined_categories

        if subcat:
            if cat_only_defined:
                suggestion = f"Add subcategory to '{cat}' in config"
            else:
                suggestion = f"Add category '{cat}' with subcategory to config"
        else:
            suggestion = f"Add category '{cat}' to config"

        if orphan.similar_categories:
            suggestion += f" or fix typo (similar: {', '.join(set(orphan.similar_categories))})"

        table.add_row(
            cat,
            subcat or "—",
            str(orphan.transaction_count),
            suggestion,
        )

    console.print(table)

    console.print(
        "\n[yellow]Action required:[/] Review these categories and either:\n"
        '  1. Add them to categories.yml: gilt category --add "Category" --write\n'
        '  2. Fix typos using: gilt recategorize --from "OldName" --to "NewName" --write\n'
    )

    return 1  # Exit code 1 indicates issues found


__all__ = ["run"]
