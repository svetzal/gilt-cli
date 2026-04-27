from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pytest

from gilt.gui.services.category_service import CategoryService
from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from gilt.model.category_io import save_categories_config
from gilt.testing.fixtures import make_group


def _write_config(path: Path) -> None:
    config = CategoryConfig(
        categories=[
            Category(
                name="Housing",
                description="Housing expenses",
                subcategories=[
                    Subcategory(name="Rent"),
                    Subcategory(name="Utilities"),
                ],
                budget=Budget(amount=2000.0, period=BudgetPeriod.monthly),
            ),
            Category(
                name="Transportation",
                budget=Budget(amount=200.0, period=BudgetPeriod.monthly),
            ),
        ]
    )
    save_categories_config(path, config)


class DescribeCategoryServiceLoading:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_path(self, temp_dir):
        path = temp_dir / "categories.yml"
        _write_config(path)
        return path

    @pytest.fixture
    def service(self, config_path):
        return CategoryService(config_path)

    def it_should_load_categories_from_config_file(self, service):
        config = service.load_categories()
        assert len(config.categories) == 2
        names = [c.name for c in config.categories]
        assert "Housing" in names
        assert "Transportation" in names

    def it_should_cache_config_after_first_load(self, service):
        first = service.load_categories()
        second = service.load_categories()
        assert first is second

    def it_should_force_reload_when_requested(self, service, config_path):
        service.load_categories()
        new_config = service.load_categories()
        new_config.categories.append(Category(name="Insurance"))
        save_categories_config(config_path, new_config)
        reloaded = service.load_categories(force_reload=True)
        assert len(reloaded.categories) == 3

    def it_should_raise_on_save_without_load(self, config_path):
        fresh = CategoryService(config_path)
        with pytest.raises(RuntimeError):
            fresh.save_categories()

    def it_should_clear_cache(self, service):
        service.load_categories()
        assert service._config is not None
        service.clear_cache()
        assert service._config is None


class DescribeCategoryServiceCategoryManagement:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_path(self, temp_dir):
        path = temp_dir / "categories.yml"
        _write_config(path)
        return path

    @pytest.fixture
    def service(self, config_path):
        return CategoryService(config_path)

    def it_should_add_a_new_category(self, service):
        service.add_category("Insurance")
        assert service.find_category("Insurance") is not None

    def it_should_raise_if_category_already_exists(self, service):
        with pytest.raises(ValueError, match="already exists"):
            service.add_category("Housing")

    def it_should_create_budget_when_amount_provided(self, service):
        service.add_category("Insurance", budget_amount=150.0)
        cat = service.find_category("Insurance")
        assert cat.budget is not None
        assert cat.budget.amount == 150.0

    def it_should_set_tax_deductible_flag(self, service):
        service.add_category("Medical", tax_deductible=True)
        cat = service.find_category("Medical")
        assert cat.tax_deductible is True

    def it_should_remove_existing_category(self, service):
        result = service.remove_category("Transportation")
        assert result is True
        assert service.find_category("Transportation") is None

    def it_should_return_false_for_nonexistent_category_removal(self, service):
        result = service.remove_category("Nonexistent")
        assert result is False

    def it_should_update_name(self, service):
        service.update_category("Housing", new_name="Dwelling")
        assert service.find_category("Dwelling") is not None
        assert service.find_category("Housing") is None

    def it_should_update_description(self, service):
        service.update_category("Housing", description="Living expenses")
        cat = service.find_category("Housing")
        assert cat.description == "Living expenses"

    def it_should_update_budget_amount_preserving_period(self, service):
        service.update_category("Housing", budget_amount=2500.0)
        cat = service.find_category("Housing")
        assert cat.budget.amount == 2500.0
        assert cat.budget.period == BudgetPeriod.monthly

    def it_should_update_budget_period_when_budget_exists(self, service):
        service.update_category("Housing", budget_period=BudgetPeriod.yearly)
        cat = service.find_category("Housing")
        assert cat.budget.period == BudgetPeriod.yearly
        assert cat.budget.amount == 2000.0

    def it_should_create_budget_when_none_exists_and_amount_provided(self, service):
        service.add_category("Dining")
        service.update_category("Dining", budget_amount=100.0)
        cat = service.find_category("Dining")
        assert cat.budget is not None
        assert cat.budget.amount == 100.0
        assert cat.budget.period == BudgetPeriod.monthly

    def it_should_update_tax_deductible(self, service):
        service.update_category("Housing", tax_deductible=True)
        cat = service.find_category("Housing")
        assert cat.tax_deductible is True

    def it_should_return_false_for_nonexistent_category_update(self, service):
        result = service.update_category("Nonexistent", new_name="Something")
        assert result is False

    def it_should_not_update_fields_that_are_none(self, service):
        cat_before = service.find_category("Housing")
        original_name = cat_before.name
        original_description = cat_before.description
        service.update_category("Housing", new_name=None, description=None)
        cat_after = service.find_category("Housing")
        assert cat_after.name == original_name
        assert cat_after.description == original_description


class DescribeCategoryServiceSubcategoryManagement:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_path(self, temp_dir):
        path = temp_dir / "categories.yml"
        _write_config(path)
        return path

    @pytest.fixture
    def service(self, config_path):
        return CategoryService(config_path)

    def it_should_add_subcategory_to_existing_category(self, service):
        result = service.add_subcategory("Housing", "Insurance")
        assert result is True
        cat = service.find_category("Housing")
        assert cat.has_subcategory("Insurance")

    def it_should_raise_if_subcategory_already_exists(self, service):
        with pytest.raises(ValueError, match="already exists"):
            service.add_subcategory("Housing", "Rent")

    def it_should_return_false_if_parent_category_not_found(self, service):
        result = service.add_subcategory("Nonexistent", "SubCat")
        assert result is False

    def it_should_remove_existing_subcategory(self, service):
        result = service.remove_subcategory("Housing", "Rent")
        assert result is True
        cat = service.find_category("Housing")
        assert not cat.has_subcategory("Rent")

    def it_should_return_false_when_removing_nonexistent_subcategory(self, service):
        result = service.remove_subcategory("Housing", "Nonexistent")
        assert result is False

    def it_should_return_false_when_removing_subcategory_from_nonexistent_category(self, service):
        result = service.remove_subcategory("Nonexistent", "Rent")
        assert result is False


class DescribeCategoryServiceUsageStats:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_path(self, temp_dir):
        path = temp_dir / "categories.yml"
        _write_config(path)
        return path

    @pytest.fixture
    def service(self, config_path):
        return CategoryService(config_path)

    def it_should_count_transactions_matching_category(self, service):
        groups = [
            make_group(category="Housing", amount=-50.0, date=date(2025, 1, 1), transaction_id="t1"),
            make_group(category="Housing", amount=-30.0, date=date(2025, 1, 2), transaction_id="t2"),
            make_group(category="Transportation", amount=-15.0, date=date(2025, 1, 3), transaction_id="t3"),
        ]
        stats = service.get_usage_stats("Housing", groups)
        assert stats["count"] == 2

    def it_should_sum_absolute_amounts(self, service):
        groups = [
            make_group(category="Housing", amount=-50.0, date=date(2025, 1, 1), transaction_id="t1"),
            make_group(category="Housing", amount=-30.0, date=date(2025, 1, 2), transaction_id="t2"),
        ]
        stats = service.get_usage_stats("Housing", groups)
        assert stats["total_amount"] == pytest.approx(80.0)

    def it_should_track_most_recent_date_as_last_used(self, service):
        groups = [
            make_group(category="Housing", amount=-50.0, date=date(2025, 1, 5), transaction_id="t1"),
            make_group(category="Housing", amount=-30.0, date=date(2025, 1, 10), transaction_id="t2"),
        ]
        stats = service.get_usage_stats("Housing", groups)
        assert stats["last_used"] == date(2025, 1, 10)

    def it_should_return_zero_count_for_unused_category(self, service):
        groups = [
            make_group(category="Transportation", amount=-15.0, date=date(2025, 1, 1), transaction_id="t1"),
        ]
        stats = service.get_usage_stats("Housing", groups)
        assert stats["count"] == 0
        assert stats["total_amount"] == 0.0
        assert stats["last_used"] is None


class DescribeCategoryServiceValidation:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_path(self, temp_dir):
        path = temp_dir / "categories.yml"
        _write_config(path)
        return path

    @pytest.fixture
    def service(self, config_path):
        return CategoryService(config_path)

    def it_should_validate_existing_category(self, service):
        assert service.validate_category_path("Housing") is True

    def it_should_validate_existing_category_and_subcategory(self, service):
        assert service.validate_category_path("Housing", "Rent") is True

    def it_should_reject_nonexistent_category(self, service):
        assert service.validate_category_path("Nonexistent") is False

    def it_should_reject_nonexistent_subcategory(self, service):
        assert service.validate_category_path("Housing", "Nonexistent") is False

    def it_should_parse_category_string_with_subcategory(self, service):
        category, subcategory = service.parse_category_string("Housing:Rent")
        assert category == "Housing"
        assert subcategory == "Rent"

    def it_should_parse_category_string_without_subcategory(self, service):
        category, subcategory = service.parse_category_string("Housing")
        assert category == "Housing"
        assert subcategory is None
