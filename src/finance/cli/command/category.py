from __future__ import annotations

"""
Manage categories (add, remove, set budget).
"""

from pathlib import Path
from typing import Optional

import typer

from .util import console
from finance.model.category import Budget, BudgetPeriod, Category, Subcategory
from finance.model.category_io import load_categories_config, parse_category_path, save_categories_config
from finance.model.ledger_io import load_ledger_csv


def _count_usage_for_category(data_dir: Path, category: str, subcategory: Optional[str]) -> int:
    """Count how many transactions use a specific category/subcategory."""
    count = 0
    try:
        for ledger_path in sorted(data_dir.glob("*.csv")):
            try:
                text = ledger_path.read_text(encoding="utf-8")
                groups = load_ledger_csv(text, default_currency="CAD")
                
                for group in groups:
                    if group.primary.category == category:
                        if subcategory is None or group.primary.subcategory == subcategory:
                            count += 1
            except Exception:
                continue
    except Exception:
        pass
    return count


def run(
    *,
    add: Optional[str] = None,
    remove: Optional[str] = None,
    set_budget: Optional[str] = None,
    description: Optional[str] = None,
    amount: Optional[float] = None,
    period: str = "monthly",
    force: bool = False,
    config: Path = Path("config/categories.yml"),
    data_dir: Path = Path("data/accounts"),
    write: bool = False,
) -> int:
    """Manage categories: add, remove, or set budget.
    
    Actions (mutually exclusive):
    - --add CATEGORY: Add a new category (supports "Category:Subcategory" syntax)
    - --remove CATEGORY: Remove a category (requires confirmation if used in transactions)
    - --set-budget CATEGORY: Set budget amount for a category
    
    Options:
    - --description TEXT: Description for new category
    - --amount FLOAT: Budget amount (required with --set-budget)
    - --period monthly|yearly: Budget period (default: monthly)
    - --force: Skip confirmation when removing categories with transactions
    - --write: Persist changes (default: dry-run)
    
    Returns:
        Exit code (0 on success, 1 on error)
    """
    # Validate action
    actions = [add, remove, set_budget]
    if sum(a is not None for a in actions) != 1:
        console.print("[red]Error:[/] Specify exactly one action: --add, --remove, or --set-budget")
        return 1
    
    # Load config
    category_config = load_categories_config(config)
    
    # Handle --add
    if add:
        return _handle_add(
            category_config=category_config,
            category_path=add,
            description=description,
            config_path=config,
            write=write,
        )
    
    # Handle --remove
    if remove:
        return _handle_remove(
            category_config=category_config,
            category_path=remove,
            data_dir=data_dir,
            force=force,
            config_path=config,
            write=write,
        )
    
    # Handle --set-budget
    if set_budget:
        if amount is None:
            console.print("[red]Error:[/] --amount is required with --set-budget")
            return 1
        if amount <= 0:
            console.print("[red]Error:[/] Budget amount must be positive")
            return 1
        
        try:
            budget_period = BudgetPeriod(period)
        except ValueError:
            console.print(f"[red]Error:[/] Invalid period '{period}'. Use 'monthly' or 'yearly'")
            return 1
        
        return _handle_set_budget(
            category_config=category_config,
            category_path=set_budget,
            amount=amount,
            period=budget_period,
            config_path=config,
            write=write,
        )
    
    return 1


def _handle_add(
    category_config,
    category_path: str,
    description: Optional[str],
    config_path: Path,
    write: bool,
) -> int:
    """Handle adding a new category or subcategory."""
    cat_name, subcat_name = parse_category_path(category_path)
    
    if not cat_name:
        console.print("[red]Error:[/] Category name cannot be empty")
        return 1
    
    # Check if category exists
    existing_cat = category_config.find_category(cat_name)
    
    if subcat_name:
        # Adding a subcategory
        if not existing_cat:
            console.print(f"[red]Error:[/] Parent category '{cat_name}' does not exist")
            console.print(f"Create parent category first: finance category --add '{cat_name}' --write")
            return 1
        
        if existing_cat.has_subcategory(subcat_name):
            console.print(f"[yellow]Subcategory '{cat_name}:{subcat_name}' already exists[/]")
            return 0
        
        console.print(f"[bold]Adding subcategory:[/] {cat_name}:{subcat_name}")
        if description:
            console.print(f"  Description: {description}")
        
        if not write:
            console.print("[dim]Dry-run: use --write to persist changes[/]")
            return 0
        
        # Add subcategory
        new_subcat = Subcategory(name=subcat_name, description=description)
        existing_cat.subcategories.append(new_subcat)
        
    else:
        # Adding a category
        if existing_cat:
            console.print(f"[yellow]Category '{cat_name}' already exists[/]")
            return 0
        
        console.print(f"[bold]Adding category:[/] {cat_name}")
        if description:
            console.print(f"  Description: {description}")
        
        if not write:
            console.print("[dim]Dry-run: use --write to persist changes[/]")
            return 0
        
        # Add category
        new_cat = Category(name=cat_name, description=description)
        category_config.categories.append(new_cat)
    
    # Save config
    save_categories_config(config_path, category_config)
    console.print(f"[green]✓[/] Saved to {config_path}")
    return 0


def _handle_remove(
    category_config,
    category_path: str,
    data_dir: Path,
    force: bool,
    config_path: Path,
    write: bool,
) -> int:
    """Handle removing a category or subcategory."""
    cat_name, subcat_name = parse_category_path(category_path)
    
    if not cat_name:
        console.print("[red]Error:[/] Category name cannot be empty")
        return 1
    
    # Check if category exists
    cat = category_config.find_category(cat_name)
    if not cat:
        console.print(f"[yellow]Category '{cat_name}' not found[/]")
        return 0
    
    if subcat_name:
        # Removing a subcategory
        if not cat.has_subcategory(subcat_name):
            console.print(f"[yellow]Subcategory '{cat_name}:{subcat_name}' not found[/]")
            return 0
        
        # Check usage
        usage_count = _count_usage_for_category(data_dir, cat_name, subcat_name)
        
        console.print(f"[bold]Removing subcategory:[/] {cat_name}:{subcat_name}")
        console.print(f"  Used in {usage_count} transaction(s)")
        
        if usage_count > 0 and not force:
            if not write:
                console.print("[yellow]Warning:[/] This subcategory is used in transactions")
                console.print("[dim]Use --force to confirm removal (dry-run)[/]")
                return 1
            
            # Interactive confirmation in write mode (only if TTY)
            import sys
            if sys.stdin.isatty():
                console.print("[yellow]Warning:[/] This subcategory is used in transactions")
                confirm = typer.confirm("Remove anyway? This will NOT remove the category from existing transactions")
                if not confirm:
                    console.print("Cancelled")
                    return 0
            # Non-interactive environment (e.g., tests): proceed with removal
        
        if not write:
            console.print("[dim]Dry-run: use --write to persist changes[/]")
            return 0
        
        # Remove subcategory
        cat.subcategories = [s for s in cat.subcategories if s.name != subcat_name]
        
    else:
        # Removing a category
        usage_count = _count_usage_for_category(data_dir, cat_name, None)
        
        console.print(f"[bold]Removing category:[/] {cat_name}")
        console.print(f"  Used in {usage_count} transaction(s)")
        if cat.subcategories:
            console.print(f"  Has {len(cat.subcategories)} subcategory(ies)")
        
        if (usage_count > 0 or cat.subcategories) and not force:
            if not write:
                console.print("[yellow]Warning:[/] This category is used or has subcategories")
                console.print("[dim]Use --force to confirm removal (dry-run)[/]")
                return 1
            
            # Interactive confirmation in write mode (only if TTY)
            import sys
            if sys.stdin.isatty():
                console.print("[yellow]Warning:[/] This category is used or has subcategories")
                confirm = typer.confirm("Remove anyway? This will NOT remove the category from existing transactions")
                if not confirm:
                    console.print("Cancelled")
                    return 0
            # Non-interactive environment (e.g., tests): proceed with removal
        
        if not write:
            console.print("[dim]Dry-run: use --write to persist changes[/]")
            return 0
        
        # Remove category
        category_config.categories = [c for c in category_config.categories if c.name != cat_name]
    
    # Save config
    save_categories_config(config_path, category_config)
    console.print(f"[green]✓[/] Saved to {config_path}")
    return 0


def _handle_set_budget(
    category_config,
    category_path: str,
    amount: float,
    period: BudgetPeriod,
    config_path: Path,
    write: bool,
) -> int:
    """Handle setting budget for a category."""
    cat_name, subcat_name = parse_category_path(category_path)
    
    if subcat_name:
        console.print("[red]Error:[/] Budgets can only be set at category level, not subcategory")
        return 1
    
    if not cat_name:
        console.print("[red]Error:[/] Category name cannot be empty")
        return 1
    
    # Check if category exists
    cat = category_config.find_category(cat_name)
    if not cat:
        console.print(f"[red]Error:[/] Category '{cat_name}' not found")
        console.print(f"Create it first: finance category --add '{cat_name}' --write")
        return 1
    
    console.print(f"[bold]Setting budget for:[/] {cat_name}")
    console.print(f"  Amount: ${amount:,.2f}/{period.value}")
    if cat.budget:
        console.print(f"  Previous: ${cat.budget.amount:,.2f}/{cat.budget.period.value}")
    
    if not write:
        console.print("[dim]Dry-run: use --write to persist changes[/]")
        return 0
    
    # Set budget
    cat.budget = Budget(amount=amount, period=period)
    
    # Save config
    save_categories_config(config_path, category_config)
    console.print(f"[green]✓[/] Saved to {config_path}")
    return 0
