from __future__ import annotations

"""
Manage categories (add, remove, set budget).
"""

from pathlib import Path
from typing import Optional

import typer

from .util import console
from finance.model.category import BudgetPeriod
from finance.model.category_io import (
    load_categories_config,
    parse_category_path,
    save_categories_config,
)
from finance.model.ledger_io import load_ledger_csv
from finance.services.category_management_service import (
    CategoryManagementService,
)
from finance.workspace import Workspace


def _load_all_transactions(data_dir: Path):
    """Load all transaction groups from ledger files."""
    groups = []
    try:
        for ledger_path in sorted(data_dir.glob("*.csv")):
            try:
                text = ledger_path.read_text(encoding="utf-8")
                ledger_groups = load_ledger_csv(text, default_currency="CAD")
                groups.extend(ledger_groups)
            except Exception:
                continue
    except Exception:
        pass
    return groups


def run(
    *,
    add: Optional[str] = None,
    remove: Optional[str] = None,
    set_budget: Optional[str] = None,
    description: Optional[str] = None,
    amount: Optional[float] = None,
    period: str = "monthly",
    force: bool = False,
    workspace: Workspace,
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
    config = workspace.categories_config
    data_dir = workspace.ledger_data_dir

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

    # Use service for business logic
    service = CategoryManagementService(category_config)
    result = service.add_category(cat_name, subcat_name, description)

    # Handle already exists case (not an error)
    if result.already_exists:
        if subcat_name:
            console.print(f"[yellow]Subcategory '{cat_name}:{subcat_name}' already exists[/]")
        else:
            console.print(f"[yellow]Category '{cat_name}' already exists[/]")
        return 0

    # Handle validation errors
    if not result.success:
        for error in result.errors:
            console.print(f"[red]Error:[/] {error}")
        if "does not exist" in " ".join(result.errors):
            console.print(
                f"Create parent category first: "
                f"finance category --add '{cat_name}' --write"
            )
        return 1

    # Success - display what will be added
    if subcat_name:
        console.print(f"[bold]Adding subcategory:[/] {cat_name}:{subcat_name}")
    else:
        console.print(f"[bold]Adding category:[/] {cat_name}")

    if description:
        console.print(f"  Description: {description}")

    if not write:
        console.print("[dim]Dry-run: use --write to persist changes[/]")
        return 0

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

    # Load all transactions for usage checking
    transaction_groups = _load_all_transactions(data_dir)

    # Use service to plan removal
    service = CategoryManagementService(category_config)
    plan = service.plan_removal(cat_name, subcat_name, transaction_groups, force)

    # Handle not found case (warning, not error)
    if plan.warnings and any("not found" in w for w in plan.warnings):
        for warning in plan.warnings:
            if "not found" in warning:
                console.print(f"[yellow]{warning}[/]")
        return 0

    # Display what will be removed
    if subcat_name:
        console.print(f"[bold]Removing subcategory:[/] {cat_name}:{subcat_name}")
    else:
        console.print(f"[bold]Removing category:[/] {cat_name}")

    console.print(f"  Used in {plan.usage.transaction_count} transaction(s)")
    if plan.has_subcategories:
        cat = category_config.find_category(cat_name)
        console.print(f"  Has {len(cat.subcategories)} subcategory(ies)")

    # Check if removal is blocked
    if not plan.can_remove:
        if not write:
            # Dry-run mode: show what force would do
            for warning in plan.warnings:
                console.print(f"[yellow]Warning:[/] {warning}")
            console.print("[dim]Use --force to confirm removal (dry-run)[/]")
            return 1

        # Write mode: ask for confirmation if interactive
        import sys
        if sys.stdin.isatty():
            for warning in plan.warnings:
                console.print(f"[yellow]Warning:[/] {warning}")
            confirm = typer.confirm(
                "Remove anyway? This will NOT remove the category "
                "from existing transactions"
            )
            if not confirm:
                console.print("Cancelled")
                return 0
        # Non-interactive environment (e.g., tests): proceed with removal

    if not write:
        console.print("[dim]Dry-run: use --write to persist changes[/]")
        return 0

    # Perform the removal
    service.remove_category(cat_name, subcat_name)

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

    # Use service for business logic
    service = CategoryManagementService(category_config)
    result = service.set_budget(cat_name, amount, period)

    # Handle errors
    if not result.success:
        for error in result.errors:
            console.print(f"[red]Error:[/] {error}")
        if "not found" in " ".join(result.errors):
            console.print(f"Create it first: finance category --add '{cat_name}' --write")
        return 1

    # Display what will be set
    console.print(f"[bold]Setting budget for:[/] {cat_name}")
    console.print(f"  Amount: ${amount:,.2f}/{period.value}")
    if result.previous_budget:
        console.print(
            f"  Previous: ${result.previous_budget.amount:,.2f}/"
            f"{result.previous_budget.period.value}"
        )

    if not write:
        console.print("[dim]Dry-run: use --write to persist changes[/]")
        return 0

    # Save config (budget already set by service)
    save_categories_config(config_path, category_config)
    console.print(f"[green]✓[/] Saved to {config_path}")
    return 0
