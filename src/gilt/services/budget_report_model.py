from __future__ import annotations

"""
Budget report data models — pure data structures for budget report generation.

No imports from other service modules; this is a leaf that both the aggregation
and rendering modules can import without creating circular dependencies.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ExpenseDetail:
    """A single expense transaction for display in a report."""

    date_str: str
    description: str
    subcategory: str
    amount: float
    account_id: str


@dataclass
class BudgetSummaryLine:
    """One row in the budget summary table — one category."""

    category_name: str
    description: str | None
    budget_amount: float | None
    actual_amount: float
    remaining: float | None
    percent_used: float | None
    is_over_budget: bool
    subcategory_actuals: dict[str, float] = field(default_factory=dict)
    subcategory_order: list[str] = field(default_factory=list)


@dataclass
class BudgetReport:
    """Complete computed budget report, ready for rendering."""

    year: int | None
    month: int | None
    generated_date: date
    lines: list[BudgetSummaryLine]
    transactions_by_category: dict[str, list[ExpenseDetail]]
    total_budgeted: float
    total_actual: float
    total_remaining: float
    percent_used: float
    over_budget_count: int


__all__ = ["BudgetReport", "BudgetSummaryLine", "ExpenseDetail"]
