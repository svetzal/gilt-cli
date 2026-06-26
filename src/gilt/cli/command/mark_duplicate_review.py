"""Interactive review loop for the mark-duplicate command."""

from __future__ import annotations

from rich.prompt import Prompt

from ..console import console


def prompt_description_choice(primary_txn: dict, duplicate_txn: dict) -> str:
    """Display both description options, prompt for a choice, and return the canonical description."""
    console.print()
    console.print("[yellow]Which description would you like to keep?[/yellow]")
    console.print(f"  1) {primary_txn['canonical_description']} [green](primary)[/green]")
    console.print(f"  2) {duplicate_txn['canonical_description']} [red](duplicate)[/red]")
    console.print()
    choice = Prompt.ask(
        "Description choice [1/2]", choices=["1", "2"], default="1", show_choices=False
    )
    canonical_description = (
        primary_txn["canonical_description"]
        if choice == "1"
        else duplicate_txn["canonical_description"]
    )
    console.print()
    return canonical_description
