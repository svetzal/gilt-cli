from __future__ import annotations

"""
Budget Reporting Service facade — composes aggregation and report assembly.

Collaborator modules:
  budget_report_model.py   — data structures (leaf, no circular imports)
  budget_aggregation.py    — pure aggregation and proration functions
  budget_report_markdown.py — Markdown serialization

No UI imports (rich, typer, PySide6). No I/O.
"""

from datetime import date

from gilt.model.account import Transaction
from gilt.model.category import CategoryConfig
from gilt.services.budget_aggregation import (
    aggregate_spending,
    collect_expense_transactions,
    find_actual_for_category,
    get_budget_for_period,
)
from gilt.services.budget_report_model import BudgetReport, BudgetSummaryLine, ExpenseDetail


class BudgetReportingService:
    """Facade for budget report generation.

    Accepts a CategoryConfig at construction time. The single public method,
    build_report, composes the pure aggregation and assembly functions.
    Never imports rich, typer, or PySide6.
    """

    def __init__(self, category_config: CategoryConfig) -> None:
        self._category_config = category_config

    def build_report(
        self,
        transactions: list[Transaction],
        *,
        year: int | None,
        month: int | None,
    ) -> BudgetReport:
        """Assemble a complete BudgetReport from a list of transactions."""
        spending = aggregate_spending(transactions, year=year, month=month)
        transactions_by_category = collect_expense_transactions(
            transactions, year=year, month=month
        )

        lines: list[BudgetSummaryLine] = []
        total_budgeted = 0.0
        total_actual = 0.0
        over_budget_count = 0

        for cat in self._category_config.categories:
            budget_amount = get_budget_for_period(cat.budget, month)
            cat_actual, subcat_actuals = find_actual_for_category(cat.name, spending)

            remaining: float | None = None
            percent_used: float | None = None
            is_over_budget = False

            if budget_amount is not None:
                remaining = budget_amount - cat_actual
                percent_used = (cat_actual / budget_amount * 100) if budget_amount > 0 else 0.0
                total_budgeted += budget_amount
                if cat_actual > budget_amount:
                    is_over_budget = True
                    over_budget_count += 1

            total_actual += cat_actual

            lines.append(
                BudgetSummaryLine(
                    category_name=cat.name,
                    description=cat.description,
                    budget_amount=budget_amount,
                    actual_amount=cat_actual,
                    remaining=remaining,
                    percent_used=percent_used,
                    is_over_budget=is_over_budget,
                    subcategory_actuals=subcat_actuals,
                    subcategory_order=[s.name for s in cat.subcategories],
                )
            )

        total_remaining = total_budgeted - total_actual
        overall_pct = (total_actual / total_budgeted * 100) if total_budgeted > 0 else 0.0

        return BudgetReport(
            year=year,
            month=month,
            generated_date=date.today(),
            lines=lines,
            transactions_by_category=transactions_by_category,
            total_budgeted=total_budgeted,
            total_actual=total_actual,
            total_remaining=total_remaining,
            percent_used=overall_pct,
            over_budget_count=over_budget_count,
        )


__all__ = [
    "BudgetReport",
    "BudgetReportingService",
    "BudgetSummaryLine",
    "ExpenseDetail",
    "aggregate_spending",
    "get_budget_for_period",
]
