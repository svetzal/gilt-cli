from __future__ import annotations

"""
Category Service - Business logic for category operations

Handles loading, saving, and manipulating category data for the GUI.
All operations remain local-only with no network I/O.
"""

from pathlib import Path
from typing import Optional

from gilt.model.category import Category, CategoryConfig, Subcategory, Budget, BudgetPeriod
from gilt.model.category_io import (
    load_categories_config,
    save_categories_config,
    parse_category_path,
)


class CategoryService:
    """Service for managing category data operations."""

    def __init__(self, config_path: Path):
        """
        Initialize category service.

        Args:
            config_path: Path to categories.yml config file
        """
        self.config_path = Path(config_path)
        self._config: Optional[CategoryConfig] = None

    def load_categories(self, force_reload: bool = False) -> CategoryConfig:
        """
        Load categories from config file.

        Args:
            force_reload: If True, reload from disk even if cached

        Returns:
            CategoryConfig instance
        """
        if self._config is None or force_reload:
            self._config = load_categories_config(self.config_path)
        return self._config

    def save_categories(self) -> None:
        """
        Save current categories to config file.

        Raises:
            RuntimeError: If categories not loaded or YAML unavailable
        """
        if self._config is None:
            raise RuntimeError("No categories loaded; call load_categories() first")

        save_categories_config(self.config_path, self._config)

    def get_all_categories(self) -> list[Category]:
        """
        Get all categories.

        Returns:
            List of Category objects
        """
        config = self.load_categories()
        return config.categories

    def find_category(self, name: str) -> Optional[Category]:
        """
        Find a category by name.

        Args:
            name: Category name

        Returns:
            Category object or None if not found
        """
        config = self.load_categories()
        return config.find_category(name)

    def add_category(
        self,
        name: str,
        description: Optional[str] = None,
        budget_amount: Optional[float] = None,
        budget_period: BudgetPeriod = BudgetPeriod.monthly,
        tax_deductible: bool = False,
    ) -> Category:
        """
        Add a new category.

        Args:
            name: Category name
            description: Optional description
            budget_amount: Optional budget amount
            budget_period: Budget period (monthly or yearly)
            tax_deductible: Whether tax deductible

        Returns:
            The created Category

        Raises:
            ValueError: If category already exists or name is invalid
        """
        config = self.load_categories()

        # Check if already exists
        if config.find_category(name):
            raise ValueError(f"Category '{name}' already exists")

        # Create budget if amount provided
        budget = None
        if budget_amount is not None:
            budget = Budget(amount=budget_amount, period=budget_period)

        # Create category
        category = Category(
            name=name,
            description=description,
            budget=budget,
            tax_deductible=tax_deductible,
        )

        # Add to config
        config.categories.append(category)

        return category

    def remove_category(self, name: str) -> bool:
        """
        Remove a category.

        Args:
            name: Category name

        Returns:
            True if removed, False if not found
        """
        config = self.load_categories()

        # Find and remove
        for i, cat in enumerate(config.categories):
            if cat.name == name:
                config.categories.pop(i)
                return True

        return False

    def update_category(
        self,
        name: str,
        new_name: Optional[str] = None,
        description: Optional[str] = None,
        budget_amount: Optional[float] = None,
        budget_period: Optional[BudgetPeriod] = None,
        tax_deductible: Optional[bool] = None,
    ) -> bool:
        """
        Update an existing category.

        Args:
            name: Current category name
            new_name: New name (if renaming)
            description: New description
            budget_amount: New budget amount
            budget_period: New budget period
            tax_deductible: New tax deductible flag

        Returns:
            True if updated, False if not found
        """
        category = self.find_category(name)
        if not category:
            return False

        # Update fields
        if new_name is not None:
            category.name = new_name
        if description is not None:
            category.description = description
        if tax_deductible is not None:
            category.tax_deductible = tax_deductible

        # Update budget
        if budget_amount is not None:
            period = budget_period or (
                category.budget.period if category.budget else BudgetPeriod.monthly
            )
            category.budget = Budget(amount=budget_amount, period=period)
        elif budget_period is not None and category.budget:
            category.budget.period = budget_period

        return True

    def add_subcategory(
        self,
        category_name: str,
        subcategory_name: str,
        description: Optional[str] = None,
    ) -> bool:
        """
        Add a subcategory to a category.

        Args:
            category_name: Parent category name
            subcategory_name: Subcategory name
            description: Optional description

        Returns:
            True if added, False if category not found

        Raises:
            ValueError: If subcategory already exists
        """
        category = self.find_category(category_name)
        if not category:
            return False

        # Check if subcategory already exists
        if category.has_subcategory(subcategory_name):
            raise ValueError(
                f"Subcategory '{subcategory_name}' already exists in '{category_name}'"
            )

        # Create and add subcategory
        subcategory = Subcategory(name=subcategory_name, description=description)
        category.subcategories.append(subcategory)

        return True

    def remove_subcategory(self, category_name: str, subcategory_name: str) -> bool:
        """
        Remove a subcategory from a category.

        Args:
            category_name: Parent category name
            subcategory_name: Subcategory name

        Returns:
            True if removed, False if not found
        """
        category = self.find_category(category_name)
        if not category:
            return False

        # Find and remove
        for i, subcat in enumerate(category.subcategories):
            if subcat.name == subcategory_name:
                category.subcategories.pop(i)
                return True

        return False

    def validate_category_path(self, category: str, subcategory: Optional[str] = None) -> bool:
        """
        Validate that a category (and optional subcategory) exists.

        Args:
            category: Category name
            subcategory: Optional subcategory name

        Returns:
            True if valid, False otherwise
        """
        config = self.load_categories()
        return config.validate_category_path(category, subcategory)

    def parse_category_string(self, category_str: str) -> tuple[str, Optional[str]]:
        """
        Parse a category string (e.g., "Housing:Utilities") into parts.

        Args:
            category_str: Category string

        Returns:
            Tuple of (category_name, subcategory_name or None)
        """
        return parse_category_path(category_str)

    def get_usage_stats(self, category_name: str, transactions) -> dict:
        """
        Get usage statistics for a category.

        Args:
            category_name: Category name
            transactions: List of TransactionGroup objects

        Returns:
            Dict with 'count', 'total_amount', 'last_used'
        """
        count = 0
        total_amount = 0.0
        last_used = None

        for group in transactions:
            if group.primary.category == category_name:
                count += 1
                total_amount += abs(group.primary.amount)
                if last_used is None or group.primary.date > last_used:
                    last_used = group.primary.date

        return {
            "count": count,
            "total_amount": total_amount,
            "last_used": last_used,
        }

    def clear_cache(self):
        """Clear the category cache."""
        self._config = None
