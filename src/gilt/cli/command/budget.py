from __future__ import annotations

"""
Budget reporting: compare actual spending vs budgeted amounts.
"""

from datetime import date

from gilt.model.errors import DATA_IO_ERRORS
from gilt.services.budget_service import BudgetService
from gilt.workspace import Workspace

from ..console import print_error
from ._errors import CommandAbort
from .budget_view import display_budget_report


def run(
    *,
    year: int | None = None,
    month: int | None = None,
    category: str | None = None,
    workspace: Workspace,
) -> int:
    """Display budget summary comparing actual spending vs budgeted amounts.

    Shows spending by category for the specified period, with budget comparison
    when budgets are defined.

    Args:
        year: Filter by year (default: current year)
        month: Filter by month (1-12, requires year)
        category: Filter to specific category
        workspace: Workspace providing config and data paths

    Returns:
        Exit code (always 0)
    """
    if year is None and month is None:
        year = date.today().year

    if month is not None and year is None:
        print_error("--month requires --year")
        raise CommandAbort(1)

    if month is not None and (month < 1 or month > 12):
        print_error("--month must be between 1 and 12")
        raise CommandAbort(1)

    budget_service = BudgetService(workspace.ledger_data_dir, workspace.categories_config)

    try:
        summary = budget_service.get_budget_summary(
            year=year,
            month=month,
            category_filter=category,
        )
    except DATA_IO_ERRORS as e:
        print_error(f"Failed to generate budget report: {e}")
        raise CommandAbort(1) from None

    display_budget_report(summary, year, month, category)

    return 0
