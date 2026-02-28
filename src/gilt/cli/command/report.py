from __future__ import annotations

"""
Generate budget reports as markdown and Word documents (.docx).

Supports yearly and monthly budget reports with export to markdown and conversion
to Word format via pandoc.
"""

import subprocess
from collections import defaultdict
from datetime import date
from pathlib import Path

from gilt.model.account import Transaction
from gilt.model.category import BudgetPeriod
from gilt.model.category_io import load_categories_config
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

from .util import console


def _aggregate_spending(
    data_dir: Path,
    year: int | None,
    month: int | None,
    projections_path: Path,
) -> dict[tuple[str, str | None], float]:
    """Aggregate spending by category/subcategory for the specified period.

    Loads from projections database, automatically excluding duplicates.

    Returns:
        Dict mapping (category, subcategory) to total amount spent
    """
    spending: dict[tuple[str, str | None], float] = defaultdict(float)

    # Check projections exist
    if not projections_path.exists():
        return dict(spending)

    # Load all transactions from projections (excludes duplicates)
    projection_builder = ProjectionBuilder(projections_path)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    for row in all_transactions:
        # Skip if no category
        if not row.get("category"):
            continue

        # Convert to Transaction object
        txn = Transaction.from_projection_row(row)

        # Filter by date
        if year is not None and txn.date.year != year:
            continue
        if month is not None and txn.date.month != month:
            continue

        # Aggregate (negative amounts are expenses)
        key = (txn.category, txn.subcategory)
        spending[key] += abs(txn.amount) if txn.amount < 0 else 0.0

    return dict(spending)


def _collect_transactions(
    data_dir: Path,
    year: int | None,
    month: int | None,
    projections_path: Path,
) -> dict[str, list[tuple]]:
    """Collect individual expense transactions grouped by category for the period.

    Loads from projections database, automatically excluding duplicates.

    Each item is a tuple: (date_str, description, subcategory, amount_abs, account_id)
    Only expense transactions (amount < 0) are included for impact on budgets.
    """
    result: dict[str, list[tuple]] = defaultdict(list)

    # Check projections exist
    if not projections_path.exists():
        return dict(result)

    # Load all transactions from projections (excludes duplicates)
    projection_builder = ProjectionBuilder(projections_path)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    for row in all_transactions:
        # Skip if no category
        if not row.get("category"):
            continue

        # Convert to Transaction object
        txn = Transaction.from_projection_row(row)

        # Filter by date
        if year is not None and txn.date.year != year:
            continue
        if month is not None and txn.date.month != month:
            continue

        # Only expenses count toward budget impact
        if txn.amount >= 0:
            continue

        result[txn.category].append(
            (
                str(txn.date),  # ISO format string
                txn.description or "",
                txn.subcategory or "",
                abs(txn.amount),
                txn.account_id or "",
            )
        )

    # Deterministic sort: by date asc, amount asc, description asc
    for _cat, items in result.items():
        items.sort(key=lambda x: (x[0], x[3], x[1]))

    return dict(result)


def _budget_for_period(cat_budget, month: int | None) -> float | None:
    """Calculate budget amount adjusted for the report period."""
    if not cat_budget:
        return None
    if month is not None:
        if cat_budget.period == BudgetPeriod.monthly:
            return cat_budget.amount
        return cat_budget.amount / 12
    if cat_budget.period == BudgetPeriod.yearly:
        return cat_budget.amount
    return cat_budget.amount * 12


def _actual_for_category(
    cat_name: str, spending: dict[tuple[str, str | None], float],
) -> tuple[float, dict[str, float]]:
    """Aggregate actual spending and subcategory breakdown for a category."""
    cat_actual = 0.0
    subcat_actuals: dict[str, float] = {}
    for (spent_cat, spent_subcat), amount in spending.items():
        if spent_cat == cat_name:
            cat_actual += amount
            if spent_subcat:
                subcat_actuals[spent_subcat] = subcat_actuals.get(spent_subcat, 0.0) + amount
    return cat_actual, subcat_actuals


def _esc_md(s: str) -> str:
    """Escape pipe characters for markdown tables."""
    return s.replace("|", "\\|")


def _generate_report_header(year: int | None, month: int | None) -> list[str]:
    """Generate report title and period header."""
    if year and month:
        title = f"Budget Report - {year}-{month:02d}"
        period_desc = f"{year}-{month:02d}"
    elif year:
        title = f"Budget Report - {year}"
        period_desc = str(year)
    else:
        title = "Budget Report"
        period_desc = "All Time"

    return [
        f"# {title}\n",
        f"**Period:** {period_desc}\n",
        f"**Generated:** {date.today().isoformat()}\n",
        "",
    ]


def _generate_summary_section(
    category_config, spending, month,
) -> tuple[list[str], float, float, int]:
    """Generate the budget summary table. Returns (lines, total_budgeted, total_actual, over_count)."""
    lines = [
        "## Budget Summary\n",
        "| Category | Budget | Actual | Remaining | % Used |",
        "|----------|--------|--------|-----------|--------|",
    ]

    total_budgeted = 0.0
    total_actual = 0.0
    over_budget_count = 0

    for cat in category_config.categories:
        budget_amount = _budget_for_period(cat.budget, month)
        cat_actual, _ = _actual_for_category(cat.name, spending)

        budget_str = f"${budget_amount:,.2f}" if budget_amount else "—"
        actual_str = f"${cat_actual:,.2f}"

        if budget_amount:
            remaining = budget_amount - cat_actual
            remaining_str = f"${remaining:,.2f}"
            pct_used = (cat_actual / budget_amount) * 100 if budget_amount > 0 else 0
            pct_str = f"{pct_used:.1f}%"
            total_budgeted += budget_amount
            if cat_actual > budget_amount:
                over_budget_count += 1
        else:
            remaining_str = "—"
            pct_str = "—"

        total_actual += cat_actual
        lines.append(f"| {cat.name} | {budget_str} | {actual_str} | {remaining_str} | {pct_str} |")

    total_remaining = total_budgeted - total_actual
    total_pct = (total_actual / total_budgeted) * 100 if total_budgeted > 0 else 0
    lines.append(
        f"| **TOTAL** | **${total_budgeted:,.2f}** | **${total_actual:,.2f}** | **${total_remaining:,.2f}** | **{total_pct:.1f}%** |"
    )
    lines.append("")

    return lines, total_budgeted, total_actual, over_budget_count


def _generate_category_detail(
    cat, spending, transactions_by_category, month,
) -> list[str]:
    """Generate the detailed breakdown for a single category."""
    budget_amount = _budget_for_period(cat.budget, month)
    cat_actual, subcat_actuals = _actual_for_category(cat.name, spending)

    if cat_actual == 0 and not budget_amount:
        return []

    lines = [f"### {cat.name}\n"]

    if cat.description:
        lines.append(f"*{cat.description}*\n")

    if budget_amount:
        remaining = budget_amount - cat_actual
        pct_used = (cat_actual / budget_amount) * 100 if budget_amount > 0 else 0
        status = (
            "⚠️ OVER BUDGET" if remaining < 0
            else "✓ On Track" if pct_used < 90
            else "⚠️ Near Limit"
        )
        lines.append(f"- **Budget:** ${budget_amount:,.2f}")
        lines.append(f"- **Actual:** ${cat_actual:,.2f}")
        lines.append(f"- **Remaining:** ${remaining:,.2f}")
        lines.append(f"- **% Used:** {pct_used:.1f}%")
        lines.append(f"- **Status:** {status}")
    else:
        lines.append(f"- **Actual:** ${cat_actual:,.2f}")

    if month is not None:
        txns = transactions_by_category.get(cat.name, [])
        if txns:
            lines.append("")
            lines.append("| Date | Description | Subcategory | Amount | Account |")
            lines.append("|------|-------------|-------------|--------|---------|")
            for d, desc, subc, amt, acct in txns:
                lines.append(
                    f"| {d} | {_esc_md(desc)} | {_esc_md(subc)} | ${amt:,.2f} | {_esc_md(acct)} |"
                )
    elif cat.subcategories and subcat_actuals:
        lines.append("\n**Subcategories:**\n")
        for subcat in cat.subcategories:
            subcat_actual = subcat_actuals.get(subcat.name, 0.0)
            if subcat_actual > 0:
                pct_of_cat = (subcat_actual / cat_actual * 100) if cat_actual > 0 else 0
                lines.append(
                    f"- {subcat.name}: ${subcat_actual:,.2f} ({pct_of_cat:.1f}% of category)"
                )

    lines.append("")
    return lines


def _generate_markdown_report(
    category_config,
    spending: dict[tuple[str, str | None], float],
    transactions_by_category: dict[str, list[tuple]],
    year: int | None,
    month: int | None,
) -> str:
    """Generate markdown-formatted budget report."""
    lines = _generate_report_header(year, month)

    summary_lines, total_budgeted, total_actual, over_budget_count = _generate_summary_section(
        category_config, spending, month,
    )
    lines.extend(summary_lines)

    lines.append("## Detailed Breakdown\n")
    for cat in category_config.categories:
        lines.extend(_generate_category_detail(cat, spending, transactions_by_category, month))

    total_remaining = total_budgeted - total_actual
    total_pct = (total_actual / total_budgeted) * 100 if total_budgeted > 0 else 0

    lines.append("---\n")
    lines.append("## Summary\n")
    lines.append(f"- **Total Budgeted:** ${total_budgeted:,.2f}")
    lines.append(f"- **Total Actual:** ${total_actual:,.2f}")
    lines.append(f"- **Total Remaining:** ${total_remaining:,.2f}")
    lines.append(f"- **Overall % Used:** {total_pct:.1f}%")

    if over_budget_count > 0:
        lines.append(
            f"\n⚠️ **{over_budget_count} categor{'y' if over_budget_count == 1 else 'ies'} over budget**"
        )

    return "\n".join(lines)


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
            console.print(f"[red]Pandoc conversion failed:[/] {result.stderr}")
            return False

        return True
    except subprocess.SubprocessError as e:
        console.print(f"[red]Error running pandoc:[/] {e}")
        return False


def _resolve_output_paths(
    output: Path | None, workspace: Workspace, year: int | None, month: int | None,
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
    markdown_content: str, markdown_path: Path, docx_path: Path, has_pandoc: bool,
) -> int:
    """Write markdown and optionally convert to docx. Returns exit code."""
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        markdown_path.write_text(markdown_content, encoding="utf-8")
        console.print(f"[green]✓[/] Written markdown report: [cyan]{markdown_path}[/]")
    except Exception as e:
        console.print(f"[red]Error writing markdown file:[/] {e}")
        return 1

    if has_pandoc:
        if _convert_to_docx(markdown_path, docx_path):
            console.print(f"[green]✓[/] Written Word document: [cyan]{docx_path}[/]")
        else:
            console.print("[yellow]Warning:[/] Markdown file created but Word conversion failed")
            return 1

    return 0


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
        console.print("[red]Error:[/] --month requires --year")
        return 1

    if month is not None and (month < 1 or month > 12):
        console.print("[red]Error:[/] --month must be between 1 and 12")
        return 1

    has_pandoc = _check_pandoc()
    if not has_pandoc:
        console.print("[yellow]Warning:[/] pandoc not found. Install pandoc to generate .docx files.")
        console.print("  macOS: brew install pandoc")
        console.print("  Linux: apt-get install pandoc or yum install pandoc")
        console.print("\nContinuing with markdown generation only...")

    category_config = load_categories_config(workspace.categories_config)
    if not category_config.categories:
        console.print("[yellow]No categories defined.[/] Create config/categories.yml first")
        return 0

    spending = _aggregate_spending(workspace.ledger_data_dir, year, month, workspace.projections_path)
    transactions_by_category = _collect_transactions(workspace.ledger_data_dir, year, month, workspace.projections_path)

    markdown_content = _generate_markdown_report(category_config, spending, transactions_by_category, year, month)

    markdown_path, docx_path = _resolve_output_paths(output, workspace, year, month)

    if not write:
        console.print("[yellow]DRY RUN[/] (use --write to persist)")
        console.print(f"\nWould write markdown to: [cyan]{markdown_path}[/]")
        if has_pandoc:
            console.print(f"Would write Word doc to: [cyan]{docx_path}[/]")
        console.print("\n[dim]--- Preview (first 500 chars) ---[/]")
        console.print(markdown_content[:500] + "..." if len(markdown_content) > 500 else markdown_content)
        console.print("[dim]--- End preview ---[/]")
        return 0

    return _write_report_files(markdown_content, markdown_path, docx_path, has_pandoc)
