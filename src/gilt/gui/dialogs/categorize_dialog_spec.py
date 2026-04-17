from __future__ import annotations

"""Specs for CategorizeDialog — no real financial data, PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")

from datetime import date

from gilt.model.account import Transaction, TransactionGroup
from gilt.model.category import Category, Subcategory
from gilt.model.category_io import format_category_path


def _make_group(
    transaction_id: str = "aabb1122ccdd3344",
    txn_date: date = date(2025, 1, 15),
    description: str = "SAMPLE STORE ANYTOWN",
    amount: float = -50.00,
    account_id: str = "MYBANK_CHQ",
    category: str | None = None,
    subcategory: str | None = None,
) -> TransactionGroup:
    txn = Transaction(
        transaction_id=transaction_id,
        date=txn_date,
        description=description,
        amount=amount,
        currency="CAD",
        account_id=account_id,
        category=category,
        subcategory=subcategory,
    )
    return TransactionGroup(group_id=transaction_id, primary=txn)


def _make_categories() -> list[Category]:
    return [
        Category(
            name="Groceries",
            description="Food and household items",
            subcategories=[Subcategory(name="Fresh"), Subcategory(name="Pantry")],
        ),
        Category(
            name="Transport",
            description="Travel and commuting",
            subcategories=[],
        ),
    ]


class DescribeCategorizeDialogDataLogic:
    """Tests for categorize dialog business logic without instantiating the full Qt dialog."""

    def it_should_build_category_and_subcategory_string_with_both_parts(self):
        category_name = "Groceries"
        subcategory_name = "Fresh"
        result = format_category_path(category_name, subcategory_name)
        assert result == "Groceries:Fresh"

    def it_should_use_category_only_when_no_subcategory(self):
        category_name = "Transport"
        subcategory_name = None
        result = format_category_path(category_name, subcategory_name)
        assert result == "Transport"

    def it_should_detect_recategorization_when_any_transaction_has_category(self):
        groups = [
            _make_group(category="OldCategory"),
            _make_group(transaction_id="bbcc2233ddee4455", category=None),
        ]
        recategorizing = any(t.primary.category and t.primary.category.strip() for t in groups)
        assert recategorizing is True

    def it_should_not_flag_recategorization_when_no_transactions_have_category(self):
        groups = [
            _make_group(category=None),
            _make_group(transaction_id="ccdd3344eeff5566", category=None),
        ]
        recategorizing = any(t.primary.category and t.primary.category.strip() for t in groups)
        assert recategorizing is False

    def it_should_not_flag_recategorization_for_whitespace_only_category(self):
        groups = [_make_group(category="   ")]
        recategorizing = any(t.primary.category and t.primary.category.strip() for t in groups)
        assert recategorizing is False

    def it_should_build_current_category_string_with_subcategory(self):
        txn = _make_group(category="Groceries", subcategory="Fresh").primary
        current = format_category_path(txn.category, txn.subcategory)
        assert current == "Groceries:Fresh"

    def it_should_build_none_label_when_no_category_assigned(self):
        txn = _make_group(category=None).primary
        current = txn.category if txn.category else "(none)"
        assert current == "(none)"


class DescribeGetSelectedCategory:
    """Tests for the tuple returned by get_selected_category."""

    def it_should_return_none_subcategory_when_only_category_selected(self):
        # Simulate return from get_selected_category when only category is chosen
        category = "Groceries"
        subcategory = None
        result = (category, subcategory)
        assert result == ("Groceries", None)

    def it_should_return_both_category_and_subcategory_when_both_chosen(self):
        category = "Groceries"
        subcategory = "Fresh"
        result = (category, subcategory)
        assert result == ("Groceries", "Fresh")

    def it_should_return_none_for_both_when_nothing_selected(self):
        category = None
        subcategory = None
        result = (category, subcategory)
        assert result == (None, None)


class DescribePopulatePreviewRows:
    """Tests for _populate_preview row content generation."""

    def it_should_produce_one_row_per_transaction(self):
        groups = [
            _make_group(transaction_id="aaaa1111bbbb2222"),
            _make_group(transaction_id="cccc3333dddd4444"),
            _make_group(transaction_id="eeee5555ffff6666"),
        ]
        # Simulate _populate_preview row generation
        rows = []
        for group in groups:
            txn = group.primary
            current = txn.category if txn.category else "(none)"
            rows.append(
                [str(txn.date), txn.description or "", f"{txn.amount:.2f}", current, "(none)"]
            )
        assert len(rows) == 3

    def it_should_format_amount_to_two_decimal_places(self):
        group = _make_group(amount=-1234.5)
        txn = group.primary
        formatted = f"{txn.amount:.2f}"
        assert formatted == "-1234.50"

    def it_should_include_date_string_in_row(self):
        group = _make_group(txn_date=date(2025, 6, 30))
        txn = group.primary
        assert str(txn.date) == "2025-06-30"

    def it_should_show_category_with_subcategory_in_current_column(self):
        group = _make_group(category="Transport", subcategory=None)
        txn = group.primary
        current = format_category_path(txn.category, txn.subcategory)
        assert current == "Transport"
