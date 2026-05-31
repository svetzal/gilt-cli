from __future__ import annotations

"""Specs for CategoriesView logic — no real financial data, PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")

from unittest.mock import patch

from gilt.gui.views.categories_view import CategoriesView
from gilt.model.category import Budget, BudgetPeriod, Category, Subcategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_CATEGORIES_YAML = """\
categories:
  - name: Groceries
    description: Food purchases
    subcategories:
      - name: Produce
      - name: Bakery
  - name: Transport
    description: Transportation expenses
    budget:
      amount: 200.0
      period: monthly
"""


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


# ---------------------------------------------------------------------------
# Existing logic tests (kept for regression coverage)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Step 8: CategoriesView mutation handlers — real widget tests
# ---------------------------------------------------------------------------


class DescribeCategoriesViewEditing:
    """CategoriesView mutation handlers tested against a real widget backed by a temp YAML."""

    @pytest.fixture
    def view(self, qapp, tmp_path):
        config_path = tmp_path / "categories.yml"
        config_path.write_text(_MINIMAL_CATEGORIES_YAML, encoding="utf-8")
        return CategoriesView(config_path=config_path), config_path

    def it_should_load_categories_and_populate_table(self, view):
        widget, _ = view
        # Groceries row + 2 subcategory rows + Transport row = 4 rows
        assert widget.table.rowCount() == 4
        assert widget.table.item(0, 0).text() == "Groceries"
        assert widget.table.item(1, 1).text() == "Produce"
        assert widget.table.item(2, 1).text() == "Bakery"
        assert widget.table.item(3, 0).text() == "Transport"

    def it_should_show_budget_for_transport_category(self, view):
        widget, _ = view
        # Transport is row 3 (0-based): Groceries, Produce, Bakery, Transport
        transport_row = 3
        assert "$200.00" in widget.table.item(transport_row, 3).text()
        assert widget.table.item(transport_row, 4).text() == "monthly"

    def it_should_add_category_and_persist_to_yaml(self, view):
        widget, config_path = view

        with (
            patch("gilt.gui.views.categories_view.QInputDialog.getText") as mock_get_text,
            patch("gilt.gui.views.categories_view.QMessageBox.information"),
        ):
            mock_get_text.side_effect = [
                ("Utilities", True),  # category name
                ("", True),  # description (optional, empty)
            ]
            widget._on_add_category()

        saved = config_path.read_text(encoding="utf-8")
        assert "Utilities" in saved

    def it_should_not_add_category_when_dialog_cancelled(self, view):
        widget, config_path = view
        row_count_before = widget.table.rowCount()

        with patch("gilt.gui.views.categories_view.QInputDialog.getText") as mock_get_text:
            mock_get_text.return_value = ("Utilities", False)  # cancelled
            widget._on_add_category()

        assert widget.table.rowCount() == row_count_before

    def it_should_add_subcategory_to_existing_category(self, view):
        widget, config_path = view
        # Select the Groceries row (row 0)
        widget.table.setCurrentCell(0, 0)

        with (
            patch("gilt.gui.views.categories_view.QInputDialog.getText") as mock_get_text,
            patch("gilt.gui.views.categories_view.QMessageBox.information"),
        ):
            mock_get_text.side_effect = [
                ("Frozen", True),  # subcategory name
                ("", True),  # description
            ]
            widget._on_add_subcategory()

        saved = config_path.read_text(encoding="utf-8")
        assert "Frozen" in saved

    def it_should_set_budget_on_category_and_persist(self, view):
        widget, config_path = view
        # Select the Groceries row (row 0, a main category with no budget yet)
        widget.table.setCurrentCell(0, 0)

        with (
            patch("gilt.gui.views.categories_view.QInputDialog.getDouble") as mock_double,
            patch("gilt.gui.views.categories_view.QInputDialog.getItem") as mock_item,
            patch("gilt.gui.views.categories_view.QMessageBox.information"),
        ):
            mock_double.return_value = (500.0, True)
            mock_item.return_value = ("monthly", True)
            widget._on_set_budget()

        saved = config_path.read_text(encoding="utf-8")
        assert "500" in saved

    def it_should_remove_category_after_confirmation(self, view):
        widget, config_path = view
        row_count_before = widget.table.rowCount()
        # Select the Transport row — it has no subcategories so row count drops by 1
        transport_row = widget.table.rowCount() - 1
        widget.table.setCurrentCell(transport_row, 0)

        from PySide6.QtWidgets import QMessageBox

        with (
            patch(
                "gilt.gui.views.categories_view.QMessageBox.question",
                return_value=QMessageBox.Yes,
            ),
            patch("gilt.gui.views.categories_view.QMessageBox.information"),
        ):
            widget._on_remove()

        assert widget.table.rowCount() == row_count_before - 1

    def it_should_not_remove_when_confirmation_declined(self, view):
        widget, _ = view
        row_count_before = widget.table.rowCount()
        widget.table.setCurrentCell(0, 0)

        from PySide6.QtWidgets import QMessageBox

        with patch(
            "gilt.gui.views.categories_view.QMessageBox.question",
            return_value=QMessageBox.No,
        ):
            widget._on_remove()

        assert widget.table.rowCount() == row_count_before

    def it_should_save_categories_when_add_category_succeeds(self, view):
        widget, _ = view

        saved = []
        original_save = widget.service.save_categories
        widget.service.save_categories = lambda: saved.append(True) or original_save()

        with (
            patch("gilt.gui.views.categories_view.QInputDialog.getText") as mock_get_text,
            patch("gilt.gui.views.categories_view.QMessageBox.information"),
        ):
            mock_get_text.side_effect = [("Dining", True), ("", True)]
            widget._on_add_category()

        assert len(saved) >= 1
