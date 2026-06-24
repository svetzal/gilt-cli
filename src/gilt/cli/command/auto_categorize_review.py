"""Interactive review loop for the auto-categorize command.

Contains the user-input controller logic: prompting, decision-handling,
and looping over predictions to build the approved list.

No business logic or persistence here — purely imperative shell for
interactive input.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from rich.prompt import Prompt

from gilt.model.category_io import build_category_from_path

from ..console import console, print_error

if TYPE_CHECKING:
    from .auto_categorize import Prediction


def handle_modify_choice(category_config, default_category: str) -> str | None:
    """Prompt user for a new category and validate it. Returns category string or None if invalid."""
    console.print("\n[dim]Available categories:[/dim]")
    for cat in category_config.categories:
        console.print(f"  - {cat.name}")
        if cat.subcategories:
            for subcat in cat.subcategories:
                console.print(f"    - {cat.name}:{subcat.name}")

    new_category = Prompt.ask(
        "\nEnter category (Category or Category:Subcategory)",
        default=default_category,
    )

    cat_name, subcat_name = build_category_from_path(new_category)
    cat_obj = next((c for c in category_config.categories if c.name == cat_name), None)

    if not cat_obj:
        print_error(f"Invalid category: {cat_name}")
        return None

    if subcat_name:
        subcat_obj = next((s for s in (cat_obj.subcategories or []) if s.name == subcat_name), None)
        if not subcat_obj:
            print_error(f"Invalid subcategory: {subcat_name}")
            return None

    return new_category


def run_interactive_review(
    predictions: list[Prediction],
    category_config,
) -> list[Prediction]:
    """Interactive review mode — approve, reject, or modify predictions.

    For each prediction prompts: (a)pprove, (r)eject, (m)odify, (q)uit.
    Returns the approved predictions.
    """
    from .auto_categorize_view import display_transaction_for_review

    console.print("\n[bold]Interactive Review Mode[/bold]")
    console.print("[dim]For each prediction: (a)pprove, (r)eject, (m)odify, (q)uit[/dim]\n")

    approved: list[Prediction] = []

    for i, p in enumerate(predictions, 1):
        display_transaction_for_review(
            i, len(predictions), p.account_id, p.txn, p.category, p.confidence
        )

        while True:
            choice = Prompt.ask(
                "\nAction",
                choices=["a", "r", "m", "q"],
                default="a",
            ).lower()

            if choice == "a":
                approved.append(p)
                console.print("[green]✓ Approved[/green]")
                break

            elif choice == "r":
                console.print("[yellow]✗ Rejected[/yellow]")
                break

            elif choice == "m":
                new_category = handle_modify_choice(category_config, p.category)
                if new_category is None:
                    continue
                approved.append(replace(p, category=new_category))
                console.print(f"[green]✓ Modified to {new_category}[/green]")
                break

            elif choice == "q":
                console.print("\n[yellow]Review interrupted[/yellow]")
                return approved

    console.print(f"\n[green]Review complete: {len(approved)}/{len(predictions)} approved[/green]")
    return approved


__all__ = ["handle_modify_choice", "run_interactive_review"]
