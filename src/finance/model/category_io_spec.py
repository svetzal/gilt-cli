from __future__ import annotations

"""
Tests for category I/O functions.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from finance.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from finance.model.category_io import load_categories_config, parse_category_path, save_categories_config


class DescribeLoadCategoriesConfig:
    """Tests for load_categories_config function."""

    def it_should_load_valid_config(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            config_path.write_text(
                """
categories:
  - name: Housing
    description: Housing expenses
    budget:
      amount: 2500.0
      period: monthly
  - name: Transportation
    subcategories:
      - name: Fuel
      - name: Maintenance
""",
                encoding="utf-8",
            )

            config = load_categories_config(config_path)
            assert len(config.categories) == 2
            assert config.categories[0].name == "Housing"
            assert config.categories[0].description == "Housing expenses"
            assert config.categories[0].budget is not None
            assert config.categories[0].budget.amount == 2500.0
            assert config.categories[1].name == "Transportation"
            assert len(config.categories[1].subcategories) == 2

    def it_should_return_empty_config_for_missing_file(self):
        config = load_categories_config(Path("/nonexistent/categories.yml"))
        assert config.categories == []

    def it_should_return_empty_config_for_invalid_yaml(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            config_path.write_text("invalid: yaml: content: [[[", encoding="utf-8")

            config = load_categories_config(config_path)
            assert config.categories == []

    def it_should_return_empty_config_for_invalid_structure(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            config_path.write_text(
                """
categories:
  - name: ""  # Invalid: empty name
""",
                encoding="utf-8",
            )

            config = load_categories_config(config_path)
            assert config.categories == []


class DescribeSaveCategoriesConfig:
    """Tests for save_categories_config function."""

    def it_should_save_valid_config(self):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Housing",
                    description="Housing expenses",
                    budget=Budget(amount=2500.0, period=BudgetPeriod.monthly),
                    subcategories=[
                        Subcategory(name="Rent", description="Monthly rent"),
                        Subcategory(name="Utilities"),
                    ],
                ),
                Category(name="Transportation"),
            ]
        )

        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            save_categories_config(config_path, config)

            assert config_path.exists()

            # Reload and verify
            loaded = load_categories_config(config_path)
            assert len(loaded.categories) == 2
            assert loaded.categories[0].name == "Housing"
            assert loaded.categories[0].budget is not None
            assert loaded.categories[0].budget.amount == 2500.0
            assert len(loaded.categories[0].subcategories) == 2
            assert loaded.categories[1].name == "Transportation"

    def it_should_create_parent_directory(self):
        config = CategoryConfig(categories=[Category(name="Test")])

        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config" / "categories.yml"
            assert not config_path.parent.exists()

            save_categories_config(config_path, config)

            assert config_path.exists()
            assert config_path.parent.exists()

    def it_should_exclude_none_values(self):
        config = CategoryConfig(
            categories=[
                Category(name="Simple"),  # No description, budget, subcategories
            ]
        )

        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            save_categories_config(config_path, config)

            content = config_path.read_text(encoding="utf-8")
            # Should not contain explicit null/None values for optional fields
            assert "description: null" not in content.lower()
            assert "budget: null" not in content.lower()


class DescribeParseCategoryPath:
    """Tests for parse_category_path function."""

    def it_should_parse_category_only(self):
        category, subcategory = parse_category_path("Housing")
        assert category == "Housing"
        assert subcategory is None

    def it_should_parse_category_with_subcategory(self):
        category, subcategory = parse_category_path("Housing:Utilities")
        assert category == "Housing"
        assert subcategory == "Utilities"

    def it_should_handle_whitespace(self):
        category, subcategory = parse_category_path("  Housing : Utilities  ")
        assert category == "Housing"
        assert subcategory == "Utilities"

    def it_should_handle_multiple_colons(self):
        # Only split on first colon
        category, subcategory = parse_category_path("Business:Meals:Client")
        assert category == "Business"
        assert subcategory == "Meals:Client"

    def it_should_handle_empty_parts(self):
        category, subcategory = parse_category_path(":")
        assert category == ""
        assert subcategory == ""
