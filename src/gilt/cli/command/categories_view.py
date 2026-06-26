"""Rich rendering functions for the categories command."""

from __future__ import annotations

from rich.table import Table

from ..console import console
from ..formatting import fmt_amount_str


def add_category_with_subcategories(table: Table, cat, usage: dict) -> None:
    """Add a bold parent summary row plus indented rows for each subcategory."""
    cat_key = (cat.name, None)
    count, total = usage.get(cat_key, (0, 0.0))

    budget_str = ""
    if cat.budget:
        budget_str = f"${cat.budget.amount:,.2f}/{cat.budget.period.value}"

    total_count = count
    total_amount = total
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

    for subcat in cat.subcategories:
        subcat_key = (cat.name, subcat.name)
        sub_count, sub_total = usage.get(subcat_key, (0, 0.0))

        table.add_row(
            "",
            f"  {subcat.name}",
            subcat.description or "",
            "",
            str(sub_count) if sub_count > 0 else "—",
            fmt_amount_str(sub_total) if sub_count > 0 else "—",
        )


def display_categories_table(category_config, usage: dict) -> None:
    """Build and print the categories Rich table plus summary line."""
    table = Table(title="Categories", show_lines=True)
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Subcategory", style="blue")
    table.add_column("Description", style="white")
    table.add_column("Budget", style="green", justify="right")
    table.add_column("Usage (Count)", style="yellow", justify="right")
    table.add_column("Usage (Total)", style="yellow", justify="right")

    for cat in category_config.categories:
        cat_key = (cat.name, None)
        count, total = usage.get(cat_key, (0, 0.0))

        budget_str = ""
        if cat.budget:
            budget_str = f"${cat.budget.amount:,.2f}/{cat.budget.period.value}"

        if not cat.subcategories:
            table.add_row(
                cat.name,
                "",
                cat.description or "",
                budget_str,
                str(count) if count > 0 else "—",
                fmt_amount_str(total) if count > 0 else "—",
            )
        else:
            add_category_with_subcategories(table, cat, usage)

    console.print(table)

    total_defined = len(category_config.categories)
    total_used = len(
        [key for key in usage if key[0] in [c.name for c in category_config.categories]]
    )
    console.print(f"\nTotal categories: {total_defined} | Used in transactions: {total_used}")
