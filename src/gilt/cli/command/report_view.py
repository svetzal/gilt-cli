"""Rich rendering functions for the report command."""

from __future__ import annotations

from pathlib import Path

from ..console import console


def print_pandoc_warning() -> None:
    """Print the warning shown when pandoc is not installed."""
    console.print(
        "[yellow]Warning:[/] pandoc not found. Install pandoc to generate .docx files."
    )
    console.print("  macOS: brew install pandoc")
    console.print("  Linux: apt-get install pandoc or yum install pandoc")
    console.print("\nContinuing with markdown generation only...")


def print_no_categories() -> None:
    """Print the message shown when no categories are defined."""
    console.print("[yellow]No categories defined.[/] Create config/categories.yml first")


def display_report_preview(
    markdown_path: Path,
    docx_path: Path,
    has_pandoc: bool,
    markdown_content: str,
) -> None:
    """Print the output paths and a truncated preview of the rendered markdown."""
    console.print(f"\nOutput markdown: [cyan]{markdown_path}[/]")
    if has_pandoc:
        console.print(f"Output Word doc: [cyan]{docx_path}[/]")
    console.print("\n[dim]--- Preview (first 500 chars) ---[/]")
    console.print(
        markdown_content[:500] + "..." if len(markdown_content) > 500 else markdown_content
    )
    console.print("[dim]--- End preview ---[/]")


def print_written_markdown(markdown_path: Path) -> None:
    """Print confirmation that the markdown report was written."""
    console.print(f"[green]✓[/] Written markdown report: [cyan]{markdown_path}[/]")


def print_written_docx(docx_path: Path) -> None:
    """Print confirmation that the Word document was written."""
    console.print(f"[green]✓[/] Written Word document: [cyan]{docx_path}[/]")


def print_docx_conversion_failed() -> None:
    """Print the warning shown when the markdown-to-docx conversion fails."""
    console.print("[yellow]Warning:[/] Markdown file created but Word conversion failed")
