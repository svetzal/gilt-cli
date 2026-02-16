from __future__ import annotations

"""
Tests for category models.
"""

import pytest
from pydantic import ValidationError

from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory


class DescribeBudget:
    """Tests for Budget model."""

    def it_should_create_valid_budget(self):
        budget = Budget(amount=500.0, period=BudgetPeriod.monthly)
        assert budget.amount == 500.0
        assert budget.period == BudgetPeriod.monthly

    def it_should_default_to_monthly_period(self):
        budget = Budget(amount=1000.0)
        assert budget.period == BudgetPeriod.monthly

    def it_should_reject_negative_amount(self):
        with pytest.raises(ValidationError):
            Budget(amount=-100.0)

    def it_should_reject_zero_amount(self):
        with pytest.raises(ValidationError):
            Budget(amount=0.0)


class DescribeSubcategory:
    """Tests for Subcategory model."""

    def it_should_create_valid_subcategory(self):
        sub = Subcategory(name="Utilities", description="Electric, gas, water")
        assert sub.name == "Utilities"
        assert sub.description == "Electric, gas, water"

    def it_should_allow_missing_description(self):
        sub = Subcategory(name="Fuel")
        assert sub.name == "Fuel"
        assert sub.description is None

    def it_should_reject_colon_in_name(self):
        with pytest.raises(ValidationError, match="cannot contain ':' character"):
            Subcategory(name="Bad:Name")

    def it_should_reject_empty_name(self):
        with pytest.raises(ValidationError):
            Subcategory(name="")


class DescribeCategory:
    """Tests for Category model."""

    def it_should_create_valid_category(self):
        cat = Category(name="Housing", description="Housing expenses")
        assert cat.name == "Housing"
        assert cat.description == "Housing expenses"
        assert cat.subcategories == []
        assert cat.budget is None
        assert cat.tax_deductible is False

    def it_should_create_category_with_subcategories(self):
        cat = Category(
            name="Housing",
            subcategories=[
                Subcategory(name="Rent"),
                Subcategory(name="Utilities"),
            ],
        )
        assert len(cat.subcategories) == 2
        assert cat.subcategories[0].name == "Rent"
        assert cat.subcategories[1].name == "Utilities"

    def it_should_create_category_with_budget(self):
        cat = Category(
            name="Dining Out",
            budget=Budget(amount=400.0, period=BudgetPeriod.monthly),
        )
        assert cat.budget is not None
        assert cat.budget.amount == 400.0
        assert cat.budget.period == BudgetPeriod.monthly

    def it_should_reject_colon_in_name(self):
        with pytest.raises(ValidationError, match="cannot contain ':' character"):
            Category(name="Bad:Name")

    def it_should_reject_empty_name(self):
        with pytest.raises(ValidationError):
            Category(name="")

    def it_should_find_existing_subcategory(self):
        cat = Category(
            name="Housing",
            subcategories=[
                Subcategory(name="Rent"),
                Subcategory(name="Utilities"),
            ],
        )
        assert cat.has_subcategory("Rent") is True
        assert cat.has_subcategory("Utilities") is True
        assert cat.has_subcategory("Mortgage") is False

    def it_should_retrieve_subcategory_by_name(self):
        cat = Category(
            name="Housing",
            subcategories=[
                Subcategory(name="Rent", description="Monthly rent"),
                Subcategory(name="Utilities"),
            ],
        )
        sub = cat.get_subcategory("Rent")
        assert sub is not None
        assert sub.name == "Rent"
        assert sub.description == "Monthly rent"

        missing = cat.get_subcategory("Mortgage")
        assert missing is None


class DescribeCategoryConfig:
    """Tests for CategoryConfig model."""

    def it_should_create_empty_config(self):
        config = CategoryConfig()
        assert config.categories == []

    def it_should_create_config_with_categories(self):
        config = CategoryConfig(
            categories=[
                Category(name="Housing"),
                Category(name="Transportation"),
            ]
        )
        assert len(config.categories) == 2

    def it_should_find_category_by_name(self):
        config = CategoryConfig(
            categories=[
                Category(name="Housing", description="Housing expenses"),
                Category(name="Transportation"),
            ]
        )
        cat = config.find_category("Housing")
        assert cat is not None
        assert cat.name == "Housing"
        assert cat.description == "Housing expenses"

        missing = config.find_category("NonExistent")
        assert missing is None

    def it_should_validate_category_path_without_subcategory(self):
        config = CategoryConfig(
            categories=[
                Category(name="Housing"),
                Category(name="Transportation"),
            ]
        )
        assert config.validate_category_path("Housing") is True
        assert config.validate_category_path("Transportation") is True
        assert config.validate_category_path("NonExistent") is False

    def it_should_validate_category_path_with_subcategory(self):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Housing",
                    subcategories=[
                        Subcategory(name="Rent"),
                        Subcategory(name="Utilities"),
                    ],
                ),
            ]
        )
        assert config.validate_category_path("Housing", "Rent") is True
        assert config.validate_category_path("Housing", "Utilities") is True
        assert config.validate_category_path("Housing", "Mortgage") is False
        assert config.validate_category_path("NonExistent", "Rent") is False
