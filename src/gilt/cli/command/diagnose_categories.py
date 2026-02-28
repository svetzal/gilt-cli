from __future__ import annotations

"""
Diagnose category issues by finding categories in transactions that aren't in config.
"""

from collections import defaultdict
from pathlib import Path

from rich.table import Table

from gilt.model.category_io import load_categories_config
from gilt.model.ledger_io import load_ledger_csv
from gilt.workspace import Workspace

from .util import console


def _collect_used_categories(data_dir: Path) -> dict[tuple[str, str | None], int]:
    """Collect all categories used in ledger files with transaction counts.

    Returns:
        Dict mapping (category, subcategory) to transaction count
    """
    used_categories: dict[tuple[str, str | None], int] = defaultdict(int)

    try:
        for ledger_path in sorted(data_dir.glob("*.csv")):
            try:
                text = ledger_path.read_text(encoding="utf-8")
                groups = load_ledger_csv(text, default_currency="CAD")

                for group in groups:
                    cat = group.primary.category
                    subcat = group.primary.subcategory

                    # Only count if category is present
                    if cat:
                        key = (cat, subcat)
                        used_categories[key] += 1
            except Exception:
                # Skip individual ledger errors
                continue
    except Exception:
        # If data_dir doesn't exist or is unreadable
        pass

    return dict(used_categories)


def _get_defined_categories(config_path: Path) -> set[tuple[str, str | None]]:
    """Get all valid category/subcategory combinations from config.

    Returns:
        Set of (category, subcategory) tuples that are valid
    """
    defined = set()

    category_config = load_categories_config(config_path)

    for cat in category_config.categories:
        # Category without subcategory is valid
        defined.add((cat.name, None))

        # Each subcategory combination is valid
        for subcat in cat.subcategories:
            defined.add((cat.name, subcat.name))

    return defined


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

    # Load defined categories
    defined_categories = _get_defined_categories(config)

    if not defined_categories:
        console.print(
            "[yellow]No categories defined in config.[/] "
            "Create config/categories.yml to define valid categories."
        )
        # Not an error condition, but nothing to compare against
        return 0

    # Collect used categories
    used_categories = _collect_used_categories(data_dir)

    if not used_categories:
        console.print("[green]No categorized transactions found.[/]")
        return 0

    # Find orphaned categories (used but not defined)
    orphaned = {}
    for (cat, subcat), count in used_categories.items():
        if (cat, subcat) not in defined_categories:
            orphaned[(cat, subcat)] = count

    if not orphaned:
        console.print("[green]✓ All categories in transactions are defined in config.[/]")
        return 0

    # Display orphaned categories
    console.print(
        f"[yellow]Found {len(orphaned)} category/subcategory combination(s) "
        f"in transactions that are not defined in categories.yml:[/]\n"
    )

    table = Table(title="Orphaned Categories", show_lines=False)
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Subcategory", style="blue")
    table.add_column("Transaction Count", style="yellow", justify="right")
    table.add_column("Suggested Action", style="white")

    # Sort by category name, then subcategory
    sorted_orphaned = sorted(orphaned.items(), key=lambda x: (x[0][0], x[0][1] or ""))

    for (cat, subcat), count in sorted_orphaned:
        # Determine suggested action
        cat_only_defined = (cat, None) in defined_categories

        if subcat:
            if cat_only_defined:
                # Category exists, but subcategory doesn't
                suggestion = f"Add subcategory to '{cat}' in config"
            else:
                # Neither category nor subcategory exists
                suggestion = f"Add category '{cat}' with subcategory to config"
        else:
            # Category without subcategory is orphaned
            suggestion = f"Add category '{cat}' to config"

        # Check if it might be a typo by looking for similar defined categories
        # (simple check: same first 3 chars)
        if len(cat) >= 3:
            similar = [
                c
                for c, s in defined_categories
                if c != cat and c.lower().startswith(cat[:3].lower())
            ]
            if similar:
                suggestion += f" or fix typo (similar: {', '.join(set(similar))})"

        table.add_row(
            cat,
            subcat or "—",
            str(count),
            suggestion,
        )

    console.print(table)

    # Summary
    console.print(
        "\n[yellow]Action required:[/] Review these categories and either:\n"
        '  1. Add them to categories.yml: gilt category --add "Category" --write\n'
        '  2. Fix typos using: gilt recategorize --from "OldName" --to "NewName" --write\n'
    )

    return 1  # Exit code 1 indicates issues found


__all__ = ["run"]
