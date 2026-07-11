from __future__ import annotations

"""
Budget aggregation — pure functions for spending aggregation and budget proration.

No I/O, no UI imports. All functions accept data directly and return plain data.
"""

from collections import defaultdict

from gilt.model.account import Transaction
from gilt.model.category import Budget, BudgetPeriod
from gilt.services.budget_report_model import ExpenseDetail


def get_budget_for_period(budget: Budget | None, month: int | None) -> float | None:
    """Return the budget amount adjusted for the report period.

    For a monthly report (month is not None):
      - monthly budget → use as-is
      - yearly budget → divide by 12

    For a yearly report (month is None):
      - yearly budget → use as-is
      - monthly budget → multiply by 12

    Returns None when no budget is defined.
    """
    if not budget:
        return None
    if month is not None:
        if budget.period == BudgetPeriod.monthly:
            return budget.amount
        return budget.amount / 12
    if budget.period == BudgetPeriod.yearly:
        return budget.amount
    return budget.amount * 12


def aggregate_spending(
    transactions: list[Transaction],
    *,
    year: int | None,
    month: int | None,
) -> dict[tuple[str, str | None], float]:
    """Sum expense amounts by (category, subcategory) for the period.

    Only negative-amount transactions (expenses) are counted.
    Transactions without a category are skipped.

    Returns a dict mapping (category, subcategory) to total absolute amount.
    """
    spending: dict[tuple[str, str | None], float] = defaultdict(float)
    for txn in transactions:
        if not txn.category:
            continue
        if year is not None and txn.date.year != year:
            continue
        if month is not None and txn.date.month != month:
            continue
        key = (txn.category, txn.subcategory)
        spending[key] += abs(txn.amount) if txn.amount < 0 else 0.0
    return dict(spending)


def find_actual_for_category(
    cat_name: str,
    spending: dict[tuple[str, str | None], float],
) -> tuple[float, dict[str, float]]:
    """Accumulate actual spending for a category from the spending dict.

    Returns a two-tuple of:
      - cat_actual: total amount spent across all subcategories
      - subcat_actuals: mapping from subcategory name to amount spent
    """
    cat_actual = 0.0
    subcat_actuals: dict[str, float] = {}
    for (spent_cat, spent_subcat), amount in spending.items():
        if spent_cat == cat_name:
            cat_actual += amount
            if spent_subcat:
                subcat_actuals[spent_subcat] = subcat_actuals.get(spent_subcat, 0.0) + amount
    return cat_actual, subcat_actuals


def collect_expense_transactions(
    transactions: list[Transaction],
    *,
    year: int | None,
    month: int | None,
) -> dict[str, list[ExpenseDetail]]:
    """Group expense transactions by category for detailed display.

    Only negative-amount (expense) transactions are included.
    Each category maps to a list of ExpenseDetail, sorted deterministically
    by (date asc, amount asc, description asc).
    """
    result: dict[str, list[ExpenseDetail]] = defaultdict(list)
    for txn in transactions:
        if not txn.category:
            continue
        if year is not None and txn.date.year != year:
            continue
        if month is not None and txn.date.month != month:
            continue
        if txn.amount >= 0:
            continue
        result[txn.category].append(
            ExpenseDetail(
                date_str=str(txn.date),
                description=txn.description or "",
                subcategory=txn.subcategory or "",
                amount=abs(txn.amount),
                account_id=txn.account_id or "",
            )
        )

    for items in result.values():
        items.sort(key=lambda x: (x.date_str, x.amount, x.description))

    return dict(result)


__all__ = [
    "aggregate_spending",
    "collect_expense_transactions",
    "find_actual_for_category",
    "get_budget_for_period",
]
