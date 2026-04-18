from __future__ import annotations

"""
Generate budget reports as markdown and Word documents (.docx).

Supports yearly and monthly budget reports with export to markdown and conversion
to Word format via pandoc.
"""

import subprocess
from datetime import date
from pathlib import Path

from gilt.model.account import Transaction
from gilt.model.category_io import load_categories_config
from gilt.services.budget_reporting_service import BudgetReportingService
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

from .util import console, print_dry_run_message, print_error


def _check_pandoc() -> bool:
    """Check if pandoc is available on the system.

    Returns:
        True if pandoc is available, False otherwise
    """
    try:
        result = subprocess.run(
            ["pandoc", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _convert_to_docx(markdown_path: Path, docx_path: Path) -> bool:
    """Convert markdown file to Word document using pandoc.

    Args:
        markdown_path: Path to source markdown file
        docx_path: Path to output .docx file

    Returns:
        True if conversion succeeded, False otherwise
    """
    try:
        result = subprocess.run(
            [
                "pandoc",
                str(markdown_path),
                "-o",
                str(docx_path),
                "--from=markdown",
                "--to=docx",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print_error(f"Pandoc conversion failed: {result.stderr}")
            return False

        return True
    except subprocess.SubprocessError as e:
        print_error(f"Error running pandoc: {e}")
        return False


def _resolve_output_paths(
    output: Path | None,
    workspace: Workspace,
    year: int | None,
    month: int | None,
) -> tuple[Path, Path]:
    """Resolve markdown and docx output paths."""
    if output is None:
        if year and month:
            base_name = f"budget_report_{year}_{month:02d}"
        elif year:
            base_name = f"budget_report_{year}"
        else:
            base_name = "budget_report"
        output = workspace.reports_dir / base_name
    return output.with_suffix(".md"), output.with_suffix(".docx")


def _write_report_files(
    markdown_content: str,
    markdown_path: Path,
    docx_path: Path,
    has_pandoc: bool,
) -> int:
    """Write markdown and optionally convert to docx. Returns exit code."""
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        markdown_path.write_text(markdown_content, encoding="utf-8")
        console.print(f"[green]✓[/] Written markdown report: [cyan]{markdown_path}[/]")
    except OSError as e:
        print_error(f"Error writing markdown file: {e}")
        return 1

    if has_pandoc:
        if _convert_to_docx(markdown_path, docx_path):
            console.print(f"[green]✓[/] Written Word document: [cyan]{docx_path}[/]")
        else:
            console.print("[yellow]Warning:[/] Markdown file created but Word conversion failed")
            return 1

    return 0


def _load_transactions(workspace: Workspace) -> list[Transaction]:
    """Load all non-duplicate transactions from projections database."""
    if not workspace.projections_path.exists():
        return []
    projection_builder = ProjectionBuilder(workspace.projections_path)
    rows = projection_builder.get_all_transactions(include_duplicates=False)
    return [Transaction.from_projection_row(row) for row in rows if row.get("category")]


def run(
    *,
    year: int | None = None,
    month: int | None = None,
    output: Path | None = None,
    workspace: Workspace,
    write: bool = False,
) -> int:
    """Generate budget report as markdown and Word document."""
    if year is None and month is None:
        year = date.today().year

    if month is not None and year is None:
        print_error("--month requires --year")
        return 1

    if month is not None and (month < 1 or month > 12):
        print_error("--month must be between 1 and 12")
        return 1

    has_pandoc = _check_pandoc()
    if not has_pandoc:
        console.print(
            "[yellow]Warning:[/] pandoc not found. Install pandoc to generate .docx files."
        )
        console.print("  macOS: brew install pandoc")
        console.print("  Linux: apt-get install pandoc or yum install pandoc")
        console.print("\nContinuing with markdown generation only...")

    category_config = load_categories_config(workspace.categories_config)
    if not category_config.categories:
        console.print("[yellow]No categories defined.[/] Create config/categories.yml first")
        return 0

    transactions = _load_transactions(workspace)
    service = BudgetReportingService(category_config)
    report = service.generate_report(transactions, year=year, month=month)
    markdown_content = service.render_markdown(report)

    markdown_path, docx_path = _resolve_output_paths(output, workspace, year, month)

    if not write:
        print_dry_run_message()
        console.print(f"\nWould write markdown to: [cyan]{markdown_path}[/]")
        if has_pandoc:
            console.print(f"Would write Word doc to: [cyan]{docx_path}[/]")
        console.print("\n[dim]--- Preview (first 500 chars) ---[/]")
        console.print(
            markdown_content[:500] + "..." if len(markdown_content) > 500 else markdown_content
        )
        console.print("[dim]--- End preview ---[/]")
        return 0

    return _write_report_files(markdown_content, markdown_path, docx_path, has_pandoc)
