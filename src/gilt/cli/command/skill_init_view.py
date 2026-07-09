"""Rich rendering functions for the skill-init command."""

from __future__ import annotations

from pathlib import Path

from ..console import console


def print_source_not_found(source_dir: Path) -> None:
    console.print(f"  Expected: {source_dir}")


def print_install_header(pkg_version: str, target_dir: Path) -> None:
    console.print(f"[bold cyan]Installing gilt skill[/] v{pkg_version}")
    console.print(f"  Target: {target_dir}\n")


def display_results(file_entries: list[dict[str, str]]) -> None:
    created = [e["path"] for e in file_entries if e["action"] == "created"]
    updated = [e["path"] for e in file_entries if e["action"] == "updated"]
    up_to_date = [e["path"] for e in file_entries if e["action"] == "up-to-date"]
    skipped = [e["path"] for e in file_entries if e["action"] == "skipped"]
    missing = [e["path"] for e in file_entries if e["action"] == "missing"]

    _report_group(created, "[green]Created:[/]", "")
    _report_group(updated, "[green]Updated:[/]", "")
    _report_group(up_to_date, "[dim]Up-to-date:[/dim]", "[dim]", suffix="[/dim]")
    if skipped:
        console.print("[yellow]Skipped (installed version is newer):[/yellow]")
        for f in skipped:
            console.print(f"  [yellow]{f}[/yellow]")
        console.print("[dim]  Use --force to overwrite.[/dim]")
    if missing:
        console.print("[red]Missing source files:[/red]")
        for f in missing:
            console.print(f"  [red]{f}[/red]")


def _report_group(files: list[str], header: str, prefix: str, suffix: str = "") -> None:
    if files:
        console.print(header)
        for f in files:
            console.print(f"  {prefix}{f}{suffix}")


__all__ = [
    "print_source_not_found",
    "print_install_header",
    "display_results",
]
