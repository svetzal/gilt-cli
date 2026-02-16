from __future__ import annotations

"""
Generate budget reports as markdown and Word documents (.docx).

Supports yearly and monthly budget reports with export to markdown and conversion
to Word format via pandoc.
"""

import subprocess
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from .util import console
from finance.workspace import Workspace
from finance.model.category import BudgetPeriod
from finance.model.category_io import load_categories_config
from finance.storage.projection import ProjectionBuilder


def _aggregate_spending(
    data_dir: Path,
    year: Optional[int],
    month: Optional[int],
    projections_path: Path,
) -> Dict[Tuple[str, Optional[str]], float]:
    """Aggregate spending by category/subcategory for the specified period.

    Loads from projections database, automatically excluding duplicates.

    Returns:
        Dict mapping (category, subcategory) to total amount spent
    """
    spending: Dict[Tuple[str, Optional[str]], float] = defaultdict(float)

    # Check projections exist
    if not projections_path.exists():
        return dict(spending)

    # Load all transactions from projections (excludes duplicates)
    projection_builder = ProjectionBuilder(projections_path)
    all_transactions = projection_builder.get_all_transactions(
        include_duplicates=False
    )

    for row in all_transactions:
        # Skip if no category
        if not row.get("category"):
            continue

        # Filter by date
        txn_date = datetime.fromisoformat(row["transaction_date"]).date()
        if year is not None and txn_date.year != year:
            continue
        if month is not None and txn_date.month != month:
            continue

        # Aggregate (negative amounts are expenses)
        amount = float(row["amount"])
        key = (row["category"], row.get("subcategory"))
        spending[key] += abs(amount) if amount < 0 else 0.0

    return dict(spending)


def _collect_transactions(
    data_dir: Path,
    year: Optional[int],
    month: Optional[int],
    projections_path: Path,
) -> Dict[str, list[tuple]]:
    """Collect individual expense transactions grouped by category for the period.

    Loads from projections database, automatically excluding duplicates.

    Each item is a tuple: (date_str, description, subcategory, amount_abs, account_id)
    Only expense transactions (amount < 0) are included for impact on budgets.
    """
    result: Dict[str, list[tuple]] = defaultdict(list)

    # Check projections exist
    if not projections_path.exists():
        return dict(result)

    # Load all transactions from projections (excludes duplicates)
    projection_builder = ProjectionBuilder(projections_path)
    all_transactions = projection_builder.get_all_transactions(
        include_duplicates=False
    )

    for row in all_transactions:
        # Skip if no category
        if not row.get("category"):
            continue

        # Filter by date
        txn_date = datetime.fromisoformat(row["transaction_date"]).date()
        if year is not None and txn_date.year != year:
            continue
        if month is not None and txn_date.month != month:
            continue

        # Only expenses count toward budget impact
        amount = float(row["amount"])
        if amount >= 0:
            continue

        result[row["category"]].append(
            (
                row["transaction_date"],  # Already ISO format
                row["canonical_description"] or "",
                row.get("subcategory") or "",
                abs(amount),
                row["account_id"] or "",
            )
        )

    # Deterministic sort: by date asc, amount asc, description asc
    for cat, items in result.items():
        items.sort(key=lambda x: (x[0], x[3], x[1]))

    return dict(result)


def _generate_markdown_report(
    category_config,
    spending: Dict[Tuple[str, Optional[str]], float],
    transactions_by_category: Dict[str, list[tuple]],
    year: Optional[int],
    month: Optional[int],
) -> str:
    """Generate markdown-formatted budget report.

    Returns:
        Markdown content as string
    """
    lines = []

    # Build title
    if year and month:
        title = f"Budget Report - {year}-{month:02d}"
        period_desc = f"{year}-{month:02d}"
    elif year:
        title = f"Budget Report - {year}"
        period_desc = str(year)
    else:
        title = "Budget Report"
        period_desc = "All Time"

    lines.append(f"# {title}\n")
    lines.append(f"**Period:** {period_desc}\n")
    lines.append(f"**Generated:** {date.today().isoformat()}\n")
    lines.append("")

    # Summary table header
    lines.append("## Budget Summary\n")
    lines.append("| Category | Budget | Actual | Remaining | % Used |")
    lines.append("|----------|--------|--------|-----------|--------|")

    total_budgeted = 0.0
    total_actual = 0.0
    over_budget_count = 0

    for cat in category_config.categories:
        # Calculate budget for period
        budget_amount = None
        if cat.budget:
            if month is not None:
                # Monthly report: use monthly budget or prorate yearly
                if cat.budget.period == BudgetPeriod.monthly:
                    budget_amount = cat.budget.amount
                else:  # yearly
                    budget_amount = cat.budget.amount / 12
            else:
                # Yearly report: use yearly budget or multiply monthly
                if cat.budget.period == BudgetPeriod.yearly:
                    budget_amount = cat.budget.amount
                else:  # monthly
                    budget_amount = cat.budget.amount * 12

        # Aggregate actual spending for this category
        cat_actual = 0.0
        for (spent_cat, spent_subcat), amount in spending.items():
            if spent_cat == cat.name:
                cat_actual += amount

        # Format budget amount
        budget_str = f"${budget_amount:,.2f}" if budget_amount else "—"
        actual_str = f"${cat_actual:,.2f}"

        # Calculate remaining and percentage
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

    # Totals (no extra separator row; multiple header separators are invalid in Markdown tables)
    total_remaining = total_budgeted - total_actual
    total_pct = (total_actual / total_budgeted) * 100 if total_budgeted > 0 else 0
    lines.append(f"| **TOTAL** | **${total_budgeted:,.2f}** | **${total_actual:,.2f}** | **${total_remaining:,.2f}** | **{total_pct:.1f}%** |")
    lines.append("")

    # Detailed breakdown by category
    lines.append("## Detailed Breakdown\n")

    for cat in category_config.categories:
        # Calculate budget for period
        budget_amount = None
        if cat.budget:
            if month is not None:
                if cat.budget.period == BudgetPeriod.monthly:
                    budget_amount = cat.budget.amount
                else:
                    budget_amount = cat.budget.amount / 12
            else:
                if cat.budget.period == BudgetPeriod.yearly:
                    budget_amount = cat.budget.amount
                else:
                    budget_amount = cat.budget.amount * 12

        # Aggregate actual spending for this category and subcategories
        cat_actual = 0.0
        subcat_actuals: Dict[str, float] = {}

        for (spent_cat, spent_subcat), amount in spending.items():
            if spent_cat == cat.name:
                cat_actual += amount
                if spent_subcat:
                    subcat_actuals[spent_subcat] = subcat_actuals.get(spent_subcat, 0.0) + amount

        # Skip categories with no spending
        if cat_actual == 0 and not budget_amount:
            continue

        lines.append(f"### {cat.name}\n")

        if cat.description:
            lines.append(f"*{cat.description}*\n")

        # Category summary
        if budget_amount:
            remaining = budget_amount - cat_actual
            pct_used = (cat_actual / budget_amount) * 100 if budget_amount > 0 else 0
            status = "⚠️ OVER BUDGET" if remaining < 0 else "✓ On Track" if pct_used < 90 else "⚠️ Near Limit"

            lines.append(f"- **Budget:** ${budget_amount:,.2f}")
            lines.append(f"- **Actual:** ${cat_actual:,.2f}")
            lines.append(f"- **Remaining:** ${remaining:,.2f}")
            lines.append(f"- **% Used:** {pct_used:.1f}%")
            lines.append(f"- **Status:** {status}")
        else:
            lines.append(f"- **Actual:** ${cat_actual:,.2f}")

        # Detailed transaction table for monthly reports
        if month is not None:
            txns = transactions_by_category.get(cat.name, [])
            if txns:
                def _esc(s: str) -> str:
                    # Escape pipe characters for markdown tables
                    return s.replace("|", "\\|")
                lines.append("")
                lines.append("| Date | Description | Subcategory | Amount | Account |")
                lines.append("|------|-------------|-------------|--------|---------|")
                for d, desc, subc, amt, acct in txns:
                    lines.append(
                        f"| {d} | {_esc(desc)} | {_esc(subc)} | ${amt:,.2f} | {_esc(acct)} |"
                    )
        else:
            # Yearly or all-time: keep subcategory breakdown when available
            if cat.subcategories and subcat_actuals:
                lines.append("\n**Subcategories:**\n")
                for subcat in cat.subcategories:
                    subcat_actual = subcat_actuals.get(subcat.name, 0.0)
                    if subcat_actual > 0:
                        pct_of_cat = (subcat_actual / cat_actual * 100) if cat_actual > 0 else 0
                        lines.append(f"- {subcat.name}: ${subcat_actual:,.2f} ({pct_of_cat:.1f}% of category)")

        lines.append("")

    # Summary footer
    lines.append("---\n")
    lines.append("## Summary\n")
    lines.append(f"- **Total Budgeted:** ${total_budgeted:,.2f}")
    lines.append(f"- **Total Actual:** ${total_actual:,.2f}")
    lines.append(f"- **Total Remaining:** ${total_remaining:,.2f}")
    lines.append(f"- **Overall % Used:** {total_pct:.1f}%")

    if over_budget_count > 0:
        lines.append(f"\n⚠️ **{over_budget_count} categor{'y' if over_budget_count == 1 else 'ies'} over budget**")

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


def run(
    *,
    year: Optional[int] = None,
    month: Optional[int] = None,
    output: Optional[Path] = None,
    workspace: Workspace,
    write: bool = False,
) -> int:
    """Generate budget report as markdown and Word document.

    Creates a budget report comparing actual spending vs budgeted amounts,
    exports to markdown, and converts to Word format (.docx) using pandoc.

    Args:
        year: Filter by year (default: current year)
        month: Filter by month (1-12, requires year)
        output: Output file path (without extension, default: reports/budget_report_YYYY[-MM])
        workspace: Workspace for resolving data paths
        write: Actually write files (default: dry-run)

    Returns:
        Exit code (0 on success, 1 on error)
    """
    # Default to current year if not specified
    if year is None and month is None:
        year = date.today().year

    # Validate month requires year
    if month is not None and year is None:
        console.print("[red]Error:[/] --month requires --year")
        return 1

    if month is not None and (month < 1 or month > 12):
        console.print("[red]Error:[/] --month must be between 1 and 12")
        return 1

    # Check pandoc availability
    if not _check_pandoc():
        console.print("[yellow]Warning:[/] pandoc not found. Install pandoc to generate .docx files.")
        console.print("  macOS: brew install pandoc")
        console.print("  Linux: apt-get install pandoc or yum install pandoc")
        console.print("  Windows: https://pandoc.org/installing.html")
        console.print("\nContinuing with markdown generation only...")
        has_pandoc = False
    else:
        has_pandoc = True

    # Load categories
    category_config = load_categories_config(workspace.categories_config)

    if not category_config.categories:
        console.print("[yellow]No categories defined.[/] Create config/categories.yml first")
        return 0

    # Aggregate spending and collect transactions (for monthly per-category tables)
    spending = _aggregate_spending(
        workspace.ledger_data_dir, year, month, workspace.projections_path
    )
    transactions_by_category = _collect_transactions(
        workspace.ledger_data_dir, year, month, workspace.projections_path
    )

    # Generate markdown report
    markdown_content = _generate_markdown_report(
        category_config,
        spending,
        transactions_by_category,
        year,
        month,
    )

    # Determine output paths
    if output is None:
        reports_dir = workspace.reports_dir
        if year and month:
            base_name = f"budget_report_{year}_{month:02d}"
        elif year:
            base_name = f"budget_report_{year}"
        else:
            base_name = "budget_report"
        output = reports_dir / base_name

    markdown_path = output.with_suffix(".md")
    docx_path = output.with_suffix(".docx")

    # Dry-run vs actual write
    if not write:
        console.print("[yellow]DRY RUN[/] (use --write to persist)")
        console.print(f"\nWould write markdown to: [cyan]{markdown_path}[/]")
        if has_pandoc:
            console.print(f"Would write Word doc to: [cyan]{docx_path}[/]")
        console.print("\n[dim]--- Preview (first 500 chars) ---[/]")
        console.print(markdown_content[:500] + "..." if len(markdown_content) > 500 else markdown_content)
        console.print("[dim]--- End preview ---[/]")
        return 0

    # Create reports directory if needed
    output.parent.mkdir(parents=True, exist_ok=True)

    # Write markdown file
    try:
        markdown_path.write_text(markdown_content, encoding="utf-8")
        console.print(f"[green]✓[/] Written markdown report: [cyan]{markdown_path}[/]")
    except Exception as e:
        console.print(f"[red]Error writing markdown file:[/] {e}")
        return 1

    # Convert to docx if pandoc is available
    if has_pandoc:
        if _convert_to_docx(markdown_path, docx_path):
            console.print(f"[green]✓[/] Written Word document: [cyan]{docx_path}[/]")
        else:
            console.print("[yellow]Warning:[/] Markdown file created but Word conversion failed")
            return 1

    return 0
