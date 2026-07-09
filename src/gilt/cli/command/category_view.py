"""Rich rendering functions for the category command."""

from __future__ import annotations

from pathlib import Path

from gilt.model.category_io import format_category_path

from ..console import console
from ..formatting import fmt_amount_str


def print_already_exists(cat_name: str, subcat_name: str | None) -> None:
    """Print the notice shown when the category/subcategory already exists."""
    if subcat_name:
        console.print(
            f"[yellow]Subcategory '{format_category_path(cat_name, subcat_name)}' already exists[/]"
        )
    else:
        console.print(f"[yellow]Category '{cat_name}' already exists[/]")


def print_create_parent_hint(cat_name: str) -> None:
    """Print the hint telling the user to create the parent category first."""
    console.print(f"Create the parent first: gilt category --add '{cat_name}' --write")


def display_add_preview(cat_name: str, subcat_name: str | None, description: str | None) -> None:
    """Print a preview of the category/subcategory that will be added."""
    if subcat_name:
        console.print(f"[bold]Adding subcategory:[/] {format_category_path(cat_name, subcat_name)}")
    else:
        console.print(f"[bold]Adding category:[/] {cat_name}")

    if description:
        console.print(f"  Description: {description}")


def print_saved(config_path: Path) -> None:
    """Print confirmation that the categories config was saved."""
    console.print(f"[green]✓[/] Saved to {config_path}")


def print_removal_warnings(warnings: list[str]) -> None:
    """Print each blocked-removal warning."""
    for warning in warnings:
        console.print(f"[yellow]Warning:[/] {warning}")


def print_force_hint() -> None:
    """Print the hint telling the user to pass --force to confirm removal."""
    console.print("[dim]Use --force to confirm removal (dry-run)[/]")


def print_cancelled() -> None:
    """Print the cancellation notice."""
    console.print("Cancelled")


def print_not_found_warning(warning: str) -> None:
    """Print the warning shown when the category/subcategory was not found."""
    console.print(f"[yellow]{warning}[/]")


def display_remove_preview(
    cat_name: str,
    subcat_name: str | None,
    usage_count: int,
    subcat_count: int | None,
) -> None:
    """Print a preview of the category/subcategory that will be removed."""
    if subcat_name:
        console.print(
            f"[bold]Removing subcategory:[/] {format_category_path(cat_name, subcat_name)}"
        )
    else:
        console.print(f"[bold]Removing category:[/] {cat_name}")

    console.print(f"  Used in {usage_count} transaction(s)")
    if subcat_count is not None:
        console.print(f"  Has {subcat_count} subcategory(ies)")


def display_set_budget_preview(
    cat_name: str,
    amount: float,
    period: str,
    previous_budget,
) -> None:
    """Print a preview of the budget that will be set for a category."""
    console.print(f"[bold]Setting budget for:[/] {cat_name}")
    console.print(f"  Amount: {fmt_amount_str(amount)}/{period}")
    if previous_budget:
        console.print(
            f"  Previous: {fmt_amount_str(previous_budget.amount)}/"
            f"{previous_budget.period.value}"
        )


def print_set_budget_create_hint(cat_name: str) -> None:
    """Print the hint telling the user to create the category before setting a budget."""
    console.print(f"Create it first: gilt category --add '{cat_name}' --write")


__all__ = [
    "print_already_exists",
    "print_create_parent_hint",
    "display_add_preview",
    "print_saved",
    "print_removal_warnings",
    "print_force_hint",
    "print_cancelled",
    "print_not_found_warning",
    "display_remove_preview",
    "display_set_budget_preview",
    "print_set_budget_create_hint",
]
