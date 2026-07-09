"""Rich rendering functions for the init command."""

from __future__ import annotations

from pathlib import Path

from ..console import console


def print_init_header(root: Path) -> None:
    console.print(f"[bold cyan]Initializing workspace:[/] {root}\n")


def display_created(created_dirs: list[str], created_files: list[str]) -> None:
    if not (created_dirs or created_files):
        return
    console.print("[green]Created:[/]")
    for d in created_dirs:
        console.print(f"  {d}")
    for f in created_files:
        console.print(f"  {f}")


def display_skipped(skipped: list[str]) -> None:
    if not skipped:
        return
    console.print("[dim]Already exists (skipped):[/dim]")
    for s in skipped:
        console.print(f"  [dim]{s}[/dim]")


def print_already_initialized() -> None:
    console.print("[green]Workspace already fully initialized.[/]")


def print_next_steps(root: Path) -> None:
    console.print(f"\n[green]Workspace ready at {root}[/]")
    console.print("\n[dim]Next steps:[/dim]")
    console.print("  1. Edit config/accounts.yml to define your bank accounts")
    console.print("  2. Drop raw bank CSVs into ingest/")
    console.print("  3. Run: gilt ingest --write")
    console.print("  4. Run: gilt migrate-to-events --write")


__all__ = [
    "print_init_header",
    "display_created",
    "display_skipped",
    "print_already_initialized",
    "print_next_steps",
]
