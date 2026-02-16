"""
Category management service - functional core for category CRUD operations.

This service extracts category management business logic from CLI commands,
making it testable without UI dependencies. It handles:
- Counting category usage in transactions
- Planning category removal with safety checks
- Adding new categories/subcategories with validation
- Setting budgets with validation

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt

All dependencies are injected. All functions return data structures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from finance.model.account import TransactionGroup
from finance.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory


@dataclass
class CategoryUsage:
    """Usage information for a category/subcategory."""

    category: str
    subcategory: Optional[str]
    transaction_count: int
    transaction_ids: list[str] = field(default_factory=list)


@dataclass
class RemovalPlan:
    """Plan for removing a category/subcategory with safety information."""

    can_remove: bool
    usage: CategoryUsage
    has_subcategories: bool
    warnings: list[str] = field(default_factory=list)


@dataclass
class AdditionResult:
    """Result of adding a category/subcategory."""

    success: bool
    already_exists: bool
    errors: list[str] = field(default_factory=list)
    added_category: Optional[str] = None
    added_subcategory: Optional[str] = None


@dataclass
class BudgetUpdateResult:
    """Result of updating a budget."""

    success: bool
    previous_budget: Optional[Budget] = None
    new_budget: Optional[Budget] = None
    errors: list[str] = field(default_factory=list)


class CategoryManagementService:
    """
    Service for category CRUD operations.

    This is the functional core - pure business logic with no I/O or UI dependencies.

    Responsibilities:
    - Count category usage in transaction data
    - Plan category removal with safety checks
    - Add categories/subcategories with validation
    - Update budgets with validation

    Does NOT:
    - Display anything to console
    - Read/write files directly (delegates to category_io)
    - Prompt users for input
    - Format output for display
    """

    def __init__(self, category_config: CategoryConfig):
        """
        Initialize category management service.

        Args:
            category_config: Category configuration to operate on
        """
        self._category_config = category_config

    def count_usage(
        self,
        category: str,
        subcategory: Optional[str],
        transaction_groups: list[TransactionGroup],
    ) -> CategoryUsage:
        """
        Count how many transactions use a specific category/subcategory.

        Args:
            category: Category name to count
            subcategory: Optional subcategory name to count
            transaction_groups: List of transaction groups to search

        Returns:
            CategoryUsage with count and transaction IDs
        """
        matching_ids: list[str] = []

        for group in transaction_groups:
            if group.primary.category == category:
                if subcategory is None or group.primary.subcategory == subcategory:
                    matching_ids.append(group.primary.transaction_id)

        return CategoryUsage(
            category=category,
            subcategory=subcategory,
            transaction_count=len(matching_ids),
            transaction_ids=matching_ids,
        )

    def plan_removal(
        self,
        category: str,
        subcategory: Optional[str],
        transaction_groups: list[TransactionGroup],
        force: bool = False,
    ) -> RemovalPlan:
        """
        Plan category/subcategory removal with safety checks.

        Args:
            category: Category name to remove
            subcategory: Optional subcategory name to remove
            transaction_groups: List of transaction groups to check usage
            force: If True, allow removal even if used or has subcategories

        Returns:
            RemovalPlan with safety information and warnings
        """
        # Check if category exists
        cat = self._category_config.find_category(category)
        if not cat:
            return RemovalPlan(
                can_remove=True,  # Nothing to remove, no-op
                usage=CategoryUsage(
                    category=category,
                    subcategory=subcategory,
                    transaction_count=0,
                    transaction_ids=[],
                ),
                has_subcategories=False,
                warnings=[f"Category '{category}' not found"],
            )

        # If removing subcategory
        if subcategory:
            if not cat.has_subcategory(subcategory):
                return RemovalPlan(
                    can_remove=True,  # Nothing to remove, no-op
                    usage=CategoryUsage(
                        category=category,
                        subcategory=subcategory,
                        transaction_count=0,
                        transaction_ids=[],
                    ),
                    has_subcategories=False,
                    warnings=[f"Subcategory '{category}:{subcategory}' not found"],
                )

            # Count usage
            usage = self.count_usage(category, subcategory, transaction_groups)

            # Check if can remove
            warnings = []
            if usage.transaction_count > 0:
                warnings.append(
                    f"Subcategory is used in {usage.transaction_count} transaction(s)"
                )

            can_remove = force or usage.transaction_count == 0

            return RemovalPlan(
                can_remove=can_remove,
                usage=usage,
                has_subcategories=False,
                warnings=warnings,
            )

        # Removing entire category
        usage = self.count_usage(category, None, transaction_groups)
        has_subcategories = len(cat.subcategories) > 0

        # Check if can remove
        warnings = []
        if usage.transaction_count > 0:
            warnings.append(
                f"Category is used in {usage.transaction_count} transaction(s)"
            )
        if has_subcategories:
            warnings.append(f"Category has {len(cat.subcategories)} subcategory(ies)")

        can_remove = force or (usage.transaction_count == 0 and not has_subcategories)

        return RemovalPlan(
            can_remove=can_remove,
            usage=usage,
            has_subcategories=has_subcategories,
            warnings=warnings,
        )

    def add_category(
        self,
        category: str,
        subcategory: Optional[str],
        description: Optional[str] = None,
    ) -> AdditionResult:
        """
        Add a new category or subcategory with validation.

        Args:
            category: Category name to add
            subcategory: Optional subcategory name to add
            description: Optional description

        Returns:
            AdditionResult with success status and error messages
        """
        if not category or not category.strip():
            return AdditionResult(
                success=False,
                already_exists=False,
                errors=["Category name cannot be empty"],
            )

        # Check if category exists
        existing_cat = self._category_config.find_category(category)

        if subcategory:
            # Adding a subcategory
            if not existing_cat:
                return AdditionResult(
                    success=False,
                    already_exists=False,
                    errors=[
                        f"Parent category '{category}' does not exist",
                        "Create parent category first",
                    ],
                )

            if existing_cat.has_subcategory(subcategory):
                return AdditionResult(
                    success=False,
                    already_exists=True,
                    errors=[f"Subcategory '{category}:{subcategory}' already exists"],
                )

            # Add subcategory
            new_subcat = Subcategory(name=subcategory, description=description)
            existing_cat.subcategories.append(new_subcat)

            return AdditionResult(
                success=True,
                already_exists=False,
                added_category=category,
                added_subcategory=subcategory,
            )

        else:
            # Adding a category
            if existing_cat:
                return AdditionResult(
                    success=False,
                    already_exists=True,
                    errors=[f"Category '{category}' already exists"],
                )

            # Add category
            new_cat = Category(name=category, description=description)
            self._category_config.categories.append(new_cat)

            return AdditionResult(
                success=True,
                already_exists=False,
                added_category=category,
            )

    def set_budget(
        self,
        category: str,
        amount: float,
        period: BudgetPeriod,
    ) -> BudgetUpdateResult:
        """
        Set or update budget for a category.

        Args:
            category: Category name
            amount: Budget amount (must be positive)
            period: Budget period (monthly or yearly)

        Returns:
            BudgetUpdateResult with success status and previous/new budgets
        """
        if not category or not category.strip():
            return BudgetUpdateResult(
                success=False,
                errors=["Category name cannot be empty"],
            )

        if amount <= 0:
            return BudgetUpdateResult(
                success=False,
                errors=["Budget amount must be positive"],
            )

        # Check if category exists
        cat = self._category_config.find_category(category)
        if not cat:
            return BudgetUpdateResult(
                success=False,
                errors=[
                    f"Category '{category}' not found",
                    "Create category first",
                ],
            )

        # Save previous budget
        previous_budget = cat.budget

        # Set new budget
        new_budget = Budget(amount=amount, period=period)
        cat.budget = new_budget

        return BudgetUpdateResult(
            success=True,
            previous_budget=previous_budget,
            new_budget=new_budget,
        )

    def remove_category(
        self,
        category: str,
        subcategory: Optional[str] = None,
    ) -> bool:
        """
        Actually remove a category/subcategory from config.

        This should only be called after plan_removal() confirms it's safe.

        Args:
            category: Category name to remove
            subcategory: Optional subcategory name to remove

        Returns:
            True if removed, False if not found
        """
        cat = self._category_config.find_category(category)
        if not cat:
            return False

        if subcategory:
            # Remove subcategory
            original_count = len(cat.subcategories)
            cat.subcategories = [
                s for s in cat.subcategories if s.name != subcategory
            ]
            return len(cat.subcategories) < original_count
        else:
            # Remove entire category
            original_count = len(self._category_config.categories)
            self._category_config.categories = [
                c for c in self._category_config.categories if c.name != category
            ]
            return len(self._category_config.categories) < original_count


__all__ = [
    "CategoryUsage",
    "RemovalPlan",
    "AdditionResult",
    "BudgetUpdateResult",
    "CategoryManagementService",
]
