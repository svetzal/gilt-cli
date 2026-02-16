from __future__ import annotations

"""
List all defined categories with usage statistics.
"""

from collections import defaultdict
from pathlib import Path
from typing import Dict, Tuple

from rich.table import Table

from .util import console
from finance.model.category_io import load_categories_config
from finance.model.ledger_io import load_ledger_csv
from finance.workspace import Workspace


def _count_category_usage(data_dir: Path) -> Dict[Tuple[str, str | None], Tuple[int, float]]:
    """Count usage of categories across all ledger files.

    Returns:
        Dict mapping (category, subcategory) to (transaction_count, total_amount)
    """
    usage: Dict[Tuple[str, str | None], Tuple[int, float]] = defaultdict(lambda: (0, 0.0))

    try:
        for ledger_path in sorted(data_dir.glob("*.csv")):
            try:
                text = ledger_path.read_text(encoding="utf-8")
                groups = load_ledger_csv(text, default_currency="CAD")

                for group in groups:
                    cat = group.primary.category
                    subcat = group.primary.subcategory
                    amount = group.primary.amount

                    if cat:  # Only count categorized transactions
                        key = (cat, subcat)
                        count, total = usage[key]
                        usage[key] = (count + 1, total + amount)
            except Exception:
                # Skip individual ledger errors
                continue
    except Exception:
        # If data_dir doesn't exist or is unreadable
        pass

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

    # Load category definitions
    category_config = load_categories_config(config)

    if not category_config.categories:
        console.print(
            "[yellow]No categories defined.[/] Create config/categories.yml to define categories."
        )
        return 0

    # Count usage across ledgers
    usage = _count_category_usage(data_dir)

    # Build table
    table = Table(title="Categories", show_lines=True)
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Subcategory", style="blue")
    table.add_column("Description", style="white")
    table.add_column("Budget", style="green", justify="right")
    table.add_column("Usage (Count)", style="yellow", justify="right")
    table.add_column("Usage (Total)", style="yellow", justify="right")

    for cat in category_config.categories:
        # Category row (without subcategory)
        cat_key = (cat.name, None)
        count, total = usage.get(cat_key, (0, 0.0))

        budget_str = ""
        if cat.budget:
            budget_str = f"${cat.budget.amount:,.2f}/{cat.budget.period.value}"

        # If no subcategories, show single row
        if not cat.subcategories:
            table.add_row(
                cat.name,
                "",
                cat.description or "",
                budget_str,
                str(count) if count > 0 else "—",
                f"${total:,.2f}" if count > 0 else "—",
            )
        else:
            # Parent category row (summary for all subcategories)
            total_count = count
            total_amount = total

            # Add counts from subcategories
            for subcat in cat.subcategories:
                subcat_key = (cat.name, subcat.name)
                sub_count, sub_total = usage.get(subcat_key, (0, 0.0))
                total_count += sub_count
                total_amount += sub_total

            table.add_row(
                f"[bold]{cat.name}[/]",
                "",
                cat.description or "",
                budget_str,
                f"[bold]{total_count}[/]" if total_count > 0 else "—",
                f"[bold]${total_amount:,.2f}[/]" if total_count > 0 else "—",
            )

            # Subcategory rows (indented)
            for subcat in cat.subcategories:
                subcat_key = (cat.name, subcat.name)
                sub_count, sub_total = usage.get(subcat_key, (0, 0.0))

                table.add_row(
                    "",
                    f"  {subcat.name}",
                    subcat.description or "",
                    "",
                    str(sub_count) if sub_count > 0 else "—",
                    f"${sub_total:,.2f}" if sub_count > 0 else "—",
                )

    console.print(table)

    # Show summary
    total_defined = len(category_config.categories)
    total_used = len([key for key in usage.keys() if key[0] in [c.name for c in category_config.categories]])
    console.print(f"\nTotal categories: {total_defined} | Used in transactions: {total_used}")

    return 0
