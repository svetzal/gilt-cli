from __future__ import annotations

"""
Category models for budgeting and transaction categorization.

Scope
- Pure Pydantic v2 models for categories, subcategories, and budgets
- Mirrors config/categories.yml structure
- No I/O operations (handled by category_io.py)

Privacy
- These models hold category metadata but perform no network I/O
- Keep usage local-only
"""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class BudgetPeriod(StrEnum):
    """Budget period types."""

    monthly = "monthly"
    yearly = "yearly"


class Budget(BaseModel):
    """Budget allocation for a category.

    Defines a spending limit for a given period (monthly or yearly).
    """

    amount: float = Field(gt=0, description="Budget amount in currency units")
    period: BudgetPeriod = Field(default=BudgetPeriod.monthly, description="Budget period")


class Subcategory(BaseModel):
    """Subcategory within a parent category.

    Provides finer-grained categorization (e.g., Housing > Utilities).
    """

    name: str = Field(min_length=1, description="Subcategory name")
    description: str | None = Field(default=None, description="Human-readable description")

    @model_validator(mode="after")
    def _validate_name(self) -> Subcategory:
        """Ensure name doesn't contain colon (reserved for category:subcategory syntax)."""
        if ":" in self.name:
            raise ValueError(f"Subcategory name cannot contain ':' character: {self.name}")
        return self


class Category(BaseModel):
    """Category definition for transaction classification.

    Categories can have optional subcategories for hierarchical classification.
    Budgets can be set at the category level (not per-subcategory).
    """

    name: str = Field(min_length=1, description="Category name")
    description: str | None = Field(default=None, description="Human-readable description")
    subcategories: list[Subcategory] = Field(
        default_factory=list, description="Optional subcategories"
    )
    budget: Budget | None = Field(default=None, description="Optional budget allocation")
    tax_deductible: bool = Field(
        default=False, description="Whether expenses in this category are tax-deductible"
    )

    @model_validator(mode="after")
    def _validate_name(self) -> Category:
        """Ensure category name doesn't contain colon (reserved for category:subcategory syntax)."""
        if ":" in self.name:
            raise ValueError(f"Category name cannot contain ':' character: {self.name}")
        return self

    def has_subcategory(self, subcategory_name: str) -> bool:
        """Check if a subcategory exists within this category."""
        return any(sub.name == subcategory_name for sub in self.subcategories)

    def get_subcategory(self, subcategory_name: str) -> Subcategory | None:
        """Retrieve a subcategory by name, or None if not found."""
        for sub in self.subcategories:
            if sub.name == subcategory_name:
                return sub
        return None


class CategoryConfig(BaseModel):
    """Root configuration for categories.

    Wraps the list of categories for clean YAML serialization.
    """

    categories: list[Category] = Field(
        default_factory=list, description="List of category definitions"
    )

    def find_category(self, name: str) -> Category | None:
        """Find a category by name."""
        for cat in self.categories:
            if cat.name == name:
                return cat
        return None

    def validate_category_path(self, category: str, subcategory: str | None = None) -> bool:
        """Validate that a category (and optional subcategory) exists.

        Args:
            category: Category name
            subcategory: Optional subcategory name

        Returns:
            True if the path is valid, False otherwise
        """
        cat = self.find_category(category)
        if not cat:
            return False
        return not (subcategory and not cat.has_subcategory(subcategory))


__all__ = [
    "Budget",
    "BudgetPeriod",
    "Category",
    "CategoryConfig",
    "Subcategory",
]
