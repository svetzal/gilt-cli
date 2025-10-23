from __future__ import annotations

"""
Budget reporting: compare actual spending vs budgeted amounts.
"""

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Tuple

from rich.table import Table

from .util import console
from finance.model.category import BudgetPeriod
from finance.model.category_io import load_categories_config
from finance.model.ledger_io import load_ledger_csv


def _aggregate_spending(
    data_dir: Path,
    year: Optional[int],
    month: Optional[int],
    category_filter: Optional[str],
) -> Dict[Tuple[str, Optional[str]], float]:
    """Aggregate spending by category/subcategory for the specified period.
    
    Returns:
        Dict mapping (category, subcategory) to total amount spent
    """
    spending: Dict[Tuple[str, Optional[str]], float] = defaultdict(float)
    
    try:
        for ledger_path in sorted(data_dir.glob("*.csv")):
            try:
                text = ledger_path.read_text(encoding="utf-8")
                groups = load_ledger_csv(text, default_currency="CAD")
                
                for group in groups:
                    t = group.primary
                    
                    # Skip if no category
                    if not t.category:
                        continue
                    
                    # Filter by category if specified
                    if category_filter and t.category != category_filter:
                        continue
                    
                    # Filter by date
                    if isinstance(t.date, date):
                        if year is not None and t.date.year != year:
                            continue
                        if month is not None and t.date.month != month:
                            continue
                    
                    # Aggregate (negative amounts are expenses)
                    key = (t.category, t.subcategory)
                    spending[key] += abs(t.amount) if t.amount < 0 else 0.0
            except Exception:
                continue
    except Exception:
        pass
    
    return dict(spending)


def run(
    *,
    year: Optional[int] = None,
    month: Optional[int] = None,
    category: Optional[str] = None,
    config: Path = Path("config/categories.yml"),
    data_dir: Path = Path("data/accounts"),
) -> int:
    """Display budget summary comparing actual spending vs budgeted amounts.
    
    Shows spending by category for the specified period, with budget comparison
    when budgets are defined.
    
    Args:
        year: Filter by year (default: current year)
        month: Filter by month (1-12, requires year)
        category: Filter to specific category
        config: Path to categories.yml
        data_dir: Directory containing ledger CSVs
        
    Returns:
        Exit code (always 0)
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
    
    # Load categories
    category_config = load_categories_config(config)
    
    if not category_config.categories:
        console.print("[yellow]No categories defined.[/] Create config/categories.yml first")
        return 0
    
    # Aggregate spending
    spending = _aggregate_spending(data_dir, year, month, category)
    
    # Build report
    _display_budget_report(category_config, spending, year, month, category)
    
    return 0


def _display_budget_report(category_config, spending, year, month, category_filter):
    """Display the budget report table."""
    # Build title
    if category_filter:
        title = f"Budget Report: {category_filter}"
    else:
        title = "Budget Report"
    
    if year and month:
        title += f" ({year}-{month:02d})"
    elif year:
        title += f" ({year})"
    
    table = Table(title=title, show_lines=True)
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Subcategory", style="blue")
    table.add_column("Budget", style="green", justify="right")
    table.add_column("Actual", style="yellow", justify="right")
    table.add_column("Remaining", style="white", justify="right")
    table.add_column("% Used", style="magenta", justify="right")
    
    total_budgeted = 0.0
    total_actual = 0.0
    over_budget_count = 0
    
    for cat in category_config.categories:
        # Skip if filtering and doesn't match
        if category_filter and cat.name != category_filter:
            continue
        
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
        subcat_actuals: Dict[str, float] = {}
        
        for (spent_cat, spent_subcat), amount in spending.items():
            if spent_cat == cat.name:
                cat_actual += amount
                if spent_subcat:
                    subcat_actuals[spent_subcat] = subcat_actuals.get(spent_subcat, 0.0) + amount
        
        # Display category row
        if not cat.subcategories:
            # Simple category without subcategories
            _add_budget_row(
                table,
                cat.name,
                None,
                budget_amount,
                cat_actual,
                bold=False,
            )
            
            if budget_amount:
                total_budgeted += budget_amount
                if cat_actual > budget_amount:
                    over_budget_count += 1
            total_actual += cat_actual
        else:
            # Category with subcategories - show parent row (summary)
            _add_budget_row(
                table,
                f"[bold]{cat.name}[/]",
                None,
                budget_amount,
                cat_actual,
                bold=True,
            )
            
            if budget_amount:
                total_budgeted += budget_amount
                if cat_actual > budget_amount:
                    over_budget_count += 1
            total_actual += cat_actual
            
            # Show subcategory rows
            for subcat in cat.subcategories:
                subcat_actual = subcat_actuals.get(subcat.name, 0.0)
                _add_budget_row(
                    table,
                    "",
                    f"  {subcat.name}",
                    None,  # No budget at subcategory level
                    subcat_actual,
                    bold=False,
                )
    
    console.print(table)
    
    # Summary
    console.print(f"\n[bold]Total Budgeted:[/] ${total_budgeted:,.2f}")
    console.print(f"[bold]Total Actual:[/] ${total_actual:,.2f}")
    
    if total_budgeted > 0:
        remaining = total_budgeted - total_actual
        pct_used = (total_actual / total_budgeted) * 100
        
        if remaining >= 0:
            console.print(f"[bold]Remaining:[/] [green]${remaining:,.2f}[/]")
        else:
            console.print(f"[bold]Over Budget:[/] [red]${abs(remaining):,.2f}[/]")
        
        console.print(f"[bold]% Used:[/] {pct_used:.1f}%")
    
    if over_budget_count > 0:
        console.print(f"\n[yellow]⚠ {over_budget_count} categor{'y' if over_budget_count == 1 else 'ies'} over budget[/]")


def _add_budget_row(
    table: Table,
    category: str,
    subcategory: Optional[str],
    budget: Optional[float],
    actual: float,
    bold: bool,
) -> None:
    """Add a row to the budget table."""
    budget_str = f"${budget:,.2f}" if budget else "—"
    actual_str = f"${actual:,.2f}" if actual > 0 else "—"
    
    if budget and actual > 0:
        remaining = budget - actual
        pct_used = (actual / budget) * 100
        
        if remaining >= 0:
            remaining_str = f"${remaining:,.2f}"
            remaining_style = "green"
        else:
            remaining_str = f"-${abs(remaining):,.2f}"
            remaining_style = "red"
        
        pct_str = f"{pct_used:.1f}%"
        if pct_used > 100:
            pct_style = "red bold"
        elif pct_used > 90:
            pct_style = "yellow"
        else:
            pct_style = "green"
    else:
        remaining_str = "—"
        remaining_style = "white"
        pct_str = "—"
        pct_style = "white"
    
    if bold:
        actual_str = f"[bold]{actual_str}[/]" if actual > 0 else "—"
    
    table.add_row(
        category,
        subcategory or "",
        budget_str,
        actual_str,
        f"[{remaining_style}]{remaining_str}[/]",
        f"[{pct_style}]{pct_str}[/]",
    )
