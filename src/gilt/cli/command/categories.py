from __future__ import annotations

"""
List all defined categories with usage statistics.
"""

from collections import defaultdict
from pathlib import Path

from gilt.model.category_io import load_categories_config
from gilt.model.ledger_repository import LedgerRepository
from gilt.workspace import Workspace

from .categories_view import display_categories_table, print_no_categories


def _count_category_usage(data_dir: Path) -> dict[tuple[str, str | None], tuple[int, float]]:
    """Count usage of categories across all ledger files.

    Returns:
        Dict mapping (category, subcategory) to (transaction_count, total_amount)
    """
    usage: dict[tuple[str, str | None], tuple[int, float]] = defaultdict(lambda: (0, 0.0))

    for group in LedgerRepository(data_dir).load_all():
        cat = group.primary.category
        subcat = group.primary.subcategory
        amount = group.primary.amount

        if cat:
            key = (cat, subcat)
            count, total = usage[key]
            usage[key] = (count + 1, total + amount)

    return dict(usage)


def run(
    *,
    workspace: Workspace,
) -> int:
    """List all defined categories with usage statistics.

    Shows categories from config/categories.yml along with transaction counts
    and total amounts from ledger files.

    Returns:
        Exit code (always 0)
    """
    config = workspace.categories_config
    data_dir = workspace.ledger_data_dir

    category_config = load_categories_config(config)

    if not category_config.categories:
        print_no_categories()
        return 0

    usage = _count_category_usage(data_dir)

    display_categories_table(category_config, usage)
    return 0
