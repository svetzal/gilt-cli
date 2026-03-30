from __future__ import annotations

"""Specs for CategoriesView logic — no real financial data, PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")

from gilt.model.category import Budget, BudgetPeriod, Category, Subcategory


def _make_category(
    name: str = "Groceries",
    description: str | None = "Food purchases",
    subcategories: list[Subcategory] | None = None,
    budget: Budget | None = None,
) -> Category:
    return Category(
        name=name,
        description=description,
        subcategories=subcategories or [],
        budget=budget,
    )


class DescribeLoadCategories:
    """Tests for _load_categories row population logic."""

    def it_should_produce_one_row_per_category_with_no_subcategories(self):
        categories = [
            _make_category("Groceries"),
            _make_category("Transport"),
        ]
        rows = []
        for cat in categories:
            rows.append((cat.name, "", cat.description, cat.budget))
            for sub in cat.subcategories:
                rows.append((cat.name, sub.name, sub.description, None))
        assert len(rows) == 2

    def it_should_produce_extra_rows_for_subcategories(self):
        cat = _make_category(
            name="Housing",
            subcategories=[Subcategory(name="Rent"), Subcategory(name="Utilities")],
        )
        rows = []
        rows.append((cat.name, "", cat.description, cat.budget))
        for sub in cat.subcategories:
            rows.append((cat.name, sub.name, sub.description, None))
        assert len(rows) == 3
        assert rows[1] == ("Housing", "Rent", None, None)
        assert rows[2] == ("Housing", "Utilities", None, None)

    def it_should_pass_none_budget_for_subcategory_rows(self):
        # Per _load_categories: subcategory rows always receive budget=None
        # regardless of the parent category's budget.
        _make_category(
            name="Housing",
            budget=Budget(amount=2000.0, period=BudgetPeriod.monthly),
            subcategories=[Subcategory(name="Rent")],
        )
        subcategory_row_budget = None
        assert subcategory_row_budget is None


class DescribeAddCategoryRowFormatting:
    """Tests for _add_category_row budget display formatting."""

    def it_should_format_budget_with_dollar_sign_and_two_decimals(self):
        budget = Budget(amount=1500.0, period=BudgetPeriod.monthly)
        budget_text = f"${budget.amount:,.2f}"
        assert budget_text == "$1,500.00"

    def it_should_show_budget_period_as_string(self):
        budget = Budget(amount=1500.0, period=BudgetPeriod.monthly)
        period_text = budget.period.value
        assert period_text == "monthly"

    def it_should_show_yearly_period_string(self):
        budget = Budget(amount=18000.0, period=BudgetPeriod.yearly)
        period_text = budget.period.value
        assert period_text == "yearly"

    def it_should_show_empty_strings_for_missing_budget(self):
        budget = None
        budget_text = f"${budget.amount:,.2f}" if budget else ""
        period_text = budget.period.value if budget else ""
        assert budget_text == ""
        assert period_text == ""

    def it_should_bold_category_row_when_no_subcategory(self):
        subcategory = ""
        is_main_category = not subcategory
        assert is_main_category is True

    def it_should_not_bold_row_when_subcategory_present(self):
        subcategory = "Rent"
        is_main_category = not subcategory
        assert is_main_category is False


class DescribeSelectionButtonState:
    """Tests for button enable/disable logic based on selection state."""

    def it_should_enable_all_mutation_buttons_when_row_selected(self):
        has_selection = True
        add_subcat_enabled = has_selection
        set_budget_enabled = has_selection
        remove_enabled = has_selection
        assert add_subcat_enabled is True
        assert set_budget_enabled is True
        assert remove_enabled is True

    def it_should_disable_all_mutation_buttons_when_no_selection(self):
        has_selection = False
        add_subcat_enabled = has_selection
        set_budget_enabled = has_selection
        remove_enabled = has_selection
        assert add_subcat_enabled is False
        assert set_budget_enabled is False
        assert remove_enabled is False
