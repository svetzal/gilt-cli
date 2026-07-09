from __future__ import annotations

"""
Manage categories (add, remove, set budget).
"""

from pathlib import Path

import typer

from gilt.model.category import BudgetPeriod
from gilt.model.category_io import (
    build_category_from_path,
    load_categories_config,
    save_categories_config,
)
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.category_management_service import (
    CategoryManagementService,
)
from gilt.workspace import Workspace

from .. import mutations
from ..console import print_error
from ._errors import CommandAbort
from .category_view import (
    display_add_preview,
    display_remove_preview,
    display_set_budget_preview,
    print_already_exists,
    print_cancelled,
    print_create_parent_hint,
    print_force_hint,
    print_not_found_warning,
    print_removal_warnings,
    print_saved,
    print_set_budget_create_hint,
)


def run(
    *,
    add: str | None = None,
    remove: str | None = None,
    set_budget: str | None = None,
    description: str | None = None,
    amount: float | None = None,
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
        print_error("Specify exactly one action: --add, --remove, or --set-budget")
        raise CommandAbort(1)

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
        return _validate_and_handle_set_budget(
            category_config, set_budget, amount, period, config, write
        )

    raise CommandAbort(1)


def _validate_and_handle_set_budget(
    category_config,
    set_budget: str,
    amount: float | None,
    period: str,
    config: Path,
    write: bool,
) -> int:
    """Validate amount and period, then dispatch to _handle_set_budget. Returns exit code."""
    if amount is None:
        print_error("--amount is required with --set-budget")
        raise CommandAbort(1)
    if amount <= 0:
        print_error("Budget amount must be positive")
        raise CommandAbort(1)

    try:
        budget_period = BudgetPeriod(period)
    except ValueError:
        print_error(f"Invalid period '{period}'. Use 'monthly' or 'yearly'")
        raise CommandAbort(1) from None

    return _handle_set_budget(
        category_config=category_config,
        category_path=set_budget,
        amount=amount,
        period=budget_period,
        config_path=config,
        write=write,
    )


def _handle_add(
    category_config,
    category_path: str,
    description: str | None,
    config_path: Path,
    write: bool,
) -> int:
    """Handle adding a new category or subcategory."""
    cat_name, subcat_name = build_category_from_path(category_path)

    # Use service for business logic
    service = CategoryManagementService(category_config)
    result = service.add_category(cat_name, subcat_name, description)

    # Handle already exists case (not an error)
    if result.already_exists:
        print_already_exists(cat_name, subcat_name)
        return 0

    # Handle validation errors
    if not result.success:
        for error in result.errors:
            print_error(error)
        if subcat_name and any("does not exist" in e for e in result.errors):
            print_create_parent_hint(cat_name)
        raise CommandAbort(1)

    def apply() -> int:
        save_categories_config(config_path, category_config)
        print_saved(config_path)
        return 0

    return mutations.run_confirmed_mutation(
        matches=[cat_name],
        display=lambda: display_add_preview(cat_name, subcat_name, description),
        confirm_prompt="",
        assume_yes=True,
        write=write,
        apply=apply,
    )


def _confirm_removal(plan, write: bool) -> int | None:
    """Handle confirmation when removal is blocked. Returns exit code or None to proceed."""
    if not write:
        print_removal_warnings(plan.warnings)
        print_force_hint()
        raise CommandAbort(1)

    import sys

    if sys.stdin.isatty():
        print_removal_warnings(plan.warnings)
        confirm = typer.confirm(
            "Remove anyway? This will NOT remove the category from existing transactions"
        )
        if not confirm:
            print_cancelled()
            return 0

    return None


def _handle_remove(
    category_config,
    category_path: str,
    data_dir: Path,
    force: bool,
    config_path: Path,
    write: bool,
) -> int:
    """Handle removing a category or subcategory."""
    cat_name, subcat_name = build_category_from_path(category_path)

    # Load all transactions for usage checking
    transaction_groups = LedgerRepository(data_dir).load_all()

    # Use service to plan removal
    service = CategoryManagementService(category_config)
    plan = service.build_removal_plan(cat_name, subcat_name, transaction_groups, force)

    # Handle not found case (warning, not error)
    if plan.warnings and any("not found" in w for w in plan.warnings):
        for warning in plan.warnings:
            if "not found" in warning:
                print_not_found_warning(warning)
        return 0

    # Display what will be removed
    subcat_count = None
    if plan.has_subcategories:
        cat = category_config.find_category(cat_name)
        subcat_count = len(cat.subcategories)
    display_remove_preview(
        cat_name, subcat_name, plan.usage.transaction_count, subcat_count
    )

    # Check if removal is blocked
    if not plan.can_remove:
        result = _confirm_removal(plan, write)
        if result is not None:
            return result

    def apply() -> int:
        service.remove_category(cat_name, subcat_name)
        save_categories_config(config_path, category_config)
        print_saved(config_path)
        return 0

    return mutations.run_confirmed_mutation(
        matches=[cat_name],
        display=lambda: None,
        confirm_prompt="",
        assume_yes=True,
        write=write,
        apply=apply,
    )


def _handle_set_budget(
    category_config,
    category_path: str,
    amount: float,
    period: BudgetPeriod,
    config_path: Path,
    write: bool,
) -> int:
    """Handle setting budget for a category."""
    cat_name, subcat_name = build_category_from_path(category_path)

    if subcat_name:
        print_error("Budgets can only be set at category level, not subcategory")
        raise CommandAbort(1)

    # Use service for business logic
    service = CategoryManagementService(category_config)
    result = service.set_budget(cat_name, amount, period)

    # Handle errors
    if not result.success:
        for error in result.errors:
            print_error(error)
        if "not found" in " ".join(result.errors):
            print_set_budget_create_hint(cat_name)
        raise CommandAbort(1)

    def apply() -> int:
        # Budget already set by service; persist config.
        save_categories_config(config_path, category_config)
        print_saved(config_path)
        return 0

    return mutations.run_confirmed_mutation(
        matches=[cat_name],
        display=lambda: display_set_budget_preview(
            cat_name, amount, period.value, result.previous_budget
        ),
        confirm_prompt="",
        assume_yes=True,
        write=write,
        apply=apply,
    )
