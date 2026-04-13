from __future__ import annotations

"""
Budget Service - Business logic for budget calculations

Provides budget vs actual calculations, spending aggregation, and trend analysis.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from gilt.model.category import Category
from gilt.model.category_io import load_categories_config
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.budget_reporting_service import (
    aggregate_spending as _aggregate_spending_pure,
)
from gilt.services.budget_reporting_service import (
    calculate_budget_for_period,
)


@dataclass
class BudgetItem:
    """A budget item with actual spending comparison."""

    category_name: str
    subcategory_name: str | None
    description: str | None
    budget_amount: float | None  # Prorated for period
    actual_amount: float
    remaining: float | None
    percent_used: float | None
    is_over_budget: bool
    is_category_header: bool  # True for main category rows


@dataclass
class BudgetSummary:
    """Summary of budget vs actual."""

    total_budgeted: float
    total_actual: float
    total_remaining: float
    percent_used: float
    over_budget_count: int
    items: list[BudgetItem]


class BudgetService:
    """Service for budget calculations and analysis."""

    def __init__(self, data_dir: Path, categories_config: Path):
        """
        Initialize the budget service.

        Args:
            data_dir: Directory containing ledger CSV files
            categories_config: Path to categories.yml
        """
        self.data_dir = data_dir
        self.categories_config = categories_config

    def get_budget_summary(
        self,
        year: int | None = None,
        month: int | None = None,
        category_filter: str | None = None,
    ) -> BudgetSummary:
        """
        Get budget summary for the specified period.

        Args:
            year: Filter by year (default: current year)
            month: Filter by month (1-12, requires year)
            category_filter: Filter to specific category

        Returns:
            BudgetSummary object
        """
        # Default to current year if not specified
        if year is None and month is None:
            year = date.today().year

        # Load categories
        category_config = load_categories_config(self.categories_config)

        # Aggregate spending
        spending = self._aggregate_spending(year, month, category_filter)

        # Build budget items
        items = []
        total_budgeted = 0.0
        total_actual = 0.0
        over_budget_count = 0

        for cat in category_config.categories:
            # Skip if filtering and doesn't match
            if category_filter and cat.name != category_filter:
                continue

            # Calculate budget for period
            budget_amount = self._calculate_budget_for_period(cat, year, month)

            # Aggregate actual spending for this category
            cat_actual = 0.0
            subcat_actuals: dict[str, float] = {}

            for (spent_cat, spent_subcat), amount in spending.items():
                if spent_cat == cat.name:
                    cat_actual += amount
                    if spent_subcat:
                        subcat_actuals[spent_subcat] = (
                            subcat_actuals.get(spent_subcat, 0.0) + amount
                        )

            # Calculate remaining and percentage
            remaining = None
            percent_used = None
            is_over_budget = False

            if budget_amount is not None and budget_amount > 0:
                remaining = budget_amount - cat_actual
                percent_used = (cat_actual / budget_amount) * 100
                is_over_budget = cat_actual > budget_amount

                total_budgeted += budget_amount
                if is_over_budget:
                    over_budget_count += 1

            total_actual += cat_actual

            # Add main category item
            items.append(
                BudgetItem(
                    category_name=cat.name,
                    subcategory_name=None,
                    description=cat.description,
                    budget_amount=budget_amount,
                    actual_amount=cat_actual,
                    remaining=remaining,
                    percent_used=percent_used,
                    is_over_budget=is_over_budget,
                    is_category_header=True,
                )
            )

            # Add subcategory items
            for subcat in cat.subcategories:
                subcat_actual = subcat_actuals.get(subcat.name, 0.0)
                items.append(
                    BudgetItem(
                        category_name=cat.name,
                        subcategory_name=subcat.name,
                        description=subcat.description,
                        budget_amount=None,  # No budget at subcategory level
                        actual_amount=subcat_actual,
                        remaining=None,
                        percent_used=None,
                        is_over_budget=False,
                        is_category_header=False,
                    )
                )

        # Calculate totals
        total_remaining = total_budgeted - total_actual
        percent_used = (total_actual / total_budgeted * 100) if total_budgeted > 0 else 0.0

        return BudgetSummary(
            total_budgeted=total_budgeted,
            total_actual=total_actual,
            total_remaining=total_remaining,
            percent_used=percent_used,
            over_budget_count=over_budget_count,
            items=items,
        )

    def _calculate_budget_for_period(
        self,
        category: Category,
        year: int | None,
        month: int | None,
    ) -> float | None:
        """
        Calculate budget amount for the specified period.

        Args:
            category: Category with budget
            year: Year (None for yearly)
            month: Month (None for yearly)

        Returns:
            Prorated budget amount or None
        """
        return calculate_budget_for_period(category.budget, month)

    def _aggregate_spending(
        self,
        year: int | None,
        month: int | None,
        category_filter: str | None,
    ) -> dict[tuple[str, str | None], float]:
        """
        Aggregate spending by category/subcategory for the specified period.

        Loads transactions from the ledger repository (I/O boundary), applies
        any category filter, then delegates pure computation to aggregate_spending.

        Args:
            year: Filter by year
            month: Filter by month
            category_filter: Filter to specific category

        Returns:
            Dict mapping (category, subcategory) to total amount spent
        """
        all_transactions = [
            group.primary
            for group in LedgerRepository(self.data_dir).load_all()
            if not category_filter or group.primary.category == category_filter
        ]
        return _aggregate_spending_pure(all_transactions, year=year, month=month)

    def get_spending_by_category(
        self,
        year: int | None = None,
        month: int | None = None,
    ) -> dict[str, float]:
        """
        Get spending aggregated by category only (no subcategories).

        Args:
            year: Filter by year
            month: Filter by month

        Returns:
            Dict mapping category name to total spent
        """
        spending = self._aggregate_spending(year, month, None)

        # Roll up to category level
        category_totals: dict[str, float] = defaultdict(float)
        for (category, _), amount in spending.items():
            category_totals[category] += amount

        return dict(category_totals)

    def get_total_spending(
        self,
        year: int | None = None,
        month: int | None = None,
    ) -> float:
        """
        Get total spending for the period.

        Args:
            year: Filter by year
            month: Filter by month

        Returns:
            Total amount spent
        """
        spending = self._aggregate_spending(year, month, None)
        return sum(spending.values())

    def get_uncategorized_count(self) -> int:
        """
        Get count of uncategorized transactions.

        Returns:
            Number of uncategorized transactions
        """
        return sum(
            1 for group in LedgerRepository(self.data_dir).load_all() if not group.primary.category
        )
