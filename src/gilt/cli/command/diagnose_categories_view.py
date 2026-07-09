"""Rich rendering functions for the diagnose-categories command."""

from __future__ import annotations

from rich.table import Table

from ..console import console


def print_no_categories_defined() -> None:
    """Print the message shown when categories.yml defines no categories."""
    console.print(
        "[yellow]No categories defined in config.[/] "
        "Create config/categories.yml to define valid categories."
    )


def print_no_categorized_transactions() -> None:
    """Print the message shown when no categorized transactions exist."""
    console.print("[green]No categorized transactions found.[/]")


def print_all_categories_defined() -> None:
    """Print the message shown when every used category is defined in config."""
    console.print("[green]✓ All categories in transactions are defined in config.[/]")


def display_orphaned_categories(result, category_config) -> None:
    """Display the orphaned categories table and action guidance."""
    console.print(
        f"[yellow]Found {len(result.orphaned_categories)} category/subcategory combination(s) "
        f"in transactions that are not defined in categories.yml:[/]\n"
    )

    table = Table(title="Orphaned Categories", show_lines=False)
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Subcategory", style="blue")
    table.add_column("Transaction Count", style="yellow", justify="right")
    table.add_column("Suggested Action", style="white")

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
