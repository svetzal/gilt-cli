from __future__ import annotations

"""
Specifications for TransactionTableModel — Qt model for displaying transactions.
"""

import pytest

pytest.importorskip("PySide6")

from datetime import date
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gilt.gui.models.transaction_model import TransactionTableModel
from gilt.testing.fixtures import make_group, make_transaction

# ---------------------------------------------------------------------------
# QApplication singleton — needed for any Qt model work
# ---------------------------------------------------------------------------


def _get_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_model(transactions: list | None = None) -> TransactionTableModel:
    _get_app()
    model = TransactionTableModel()
    if transactions is not None:
        model.update_transactions(transactions)
    return model


def _index(model: TransactionTableModel, row: int, col: int):
    return model.index(row, col)


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------


class DescribeTransactionTableModelUpdateTransactions:
    """update_transactions() replaces the data and adjusts row count."""

    def it_should_report_zero_rows_when_empty(self):
        model = _make_model([])
        assert model.rowCount() == 0

    def it_should_report_correct_row_count_after_update(self):
        groups = [
            make_group(transaction_id=f"id{i:016}", date=date(2025, 1, i + 1), amount=-10.0)
            for i in range(3)
        ]
        model = _make_model(groups)
        assert model.rowCount() == 3

    def it_should_replace_existing_data_on_second_update(self):
        model = _make_model([make_group()])
        assert model.rowCount() == 1
        model.update_transactions([])
        assert model.rowCount() == 0


class DescribeTransactionTableModelDisplayRole:
    """data() with DisplayRole returns human-readable strings."""

    def it_should_display_date_as_string(self):
        model = _make_model([make_group(date=date(2025, 6, 15))])
        val = model.data(_index(model, 0, TransactionTableModel.COL_DATE), Qt.DisplayRole)
        assert "2025-06-15" in str(val)

    def it_should_display_account_id(self):
        model = _make_model([make_group(account_id="MYBANK_CHQ")])
        val = model.data(_index(model, 0, TransactionTableModel.COL_ACCOUNT), Qt.DisplayRole)
        assert val == "MYBANK_CHQ"

    def it_should_display_description(self):
        model = _make_model([make_group(description="ACME CORP PURCHASE")])
        val = model.data(_index(model, 0, TransactionTableModel.COL_DESCRIPTION), Qt.DisplayRole)
        assert val == "ACME CORP PURCHASE"

    def it_should_display_amount_with_two_decimal_places(self):
        model = _make_model([make_group(amount=-42.50)])
        val = model.data(_index(model, 0, TransactionTableModel.COL_AMOUNT), Qt.DisplayRole)
        assert val == "-42.50"

    def it_should_display_currency(self):
        model = _make_model([make_group(currency="CAD")])
        val = model.data(_index(model, 0, TransactionTableModel.COL_CURRENCY), Qt.DisplayRole)
        assert val == "CAD"

    def it_should_default_currency_to_cad_when_none(self):
        txn = make_transaction(currency=None)
        model = _make_model([make_group(primary=txn)])
        val = model.data(_index(model, 0, TransactionTableModel.COL_CURRENCY), Qt.DisplayRole)
        assert val == "CAD"

    def it_should_display_category_without_subcategory(self):
        model = _make_model([make_group(category="Housing")])
        val = model.data(_index(model, 0, TransactionTableModel.COL_CATEGORY), Qt.DisplayRole)
        assert val == "Housing"

    def it_should_display_category_colon_subcategory_when_both_set(self):
        model = _make_model([make_group(category="Housing", subcategory="Rent")])
        val = model.data(_index(model, 0, TransactionTableModel.COL_CATEGORY), Qt.DisplayRole)
        assert val == "Housing: Rent"

    def it_should_display_empty_string_when_no_category(self):
        model = _make_model([make_group(category=None)])
        val = model.data(_index(model, 0, TransactionTableModel.COL_CATEGORY), Qt.DisplayRole)
        assert val == ""

    def it_should_display_notes(self):
        model = _make_model([make_group(notes="Checked by user")])
        val = model.data(_index(model, 0, TransactionTableModel.COL_NOTES), Qt.DisplayRole)
        assert val == "Checked by user"

    def it_should_display_empty_string_when_no_notes(self):
        model = _make_model([make_group(notes=None)])
        val = model.data(_index(model, 0, TransactionTableModel.COL_NOTES), Qt.DisplayRole)
        assert val == ""

    def it_should_return_none_for_invalid_index(self):
        model = _make_model([])
        invalid = model.index(99, 0)
        val = model.data(invalid, Qt.DisplayRole)
        assert val is None


class DescribeTransactionTableModelSortRole:
    """data() with SortRole returns sortable keys."""

    def it_should_return_date_object_for_date_column(self):
        model = _make_model([make_group(date=date(2025, 5, 20))])
        val = model.data(
            _index(model, 0, TransactionTableModel.COL_DATE), TransactionTableModel.SortRole
        )
        assert val == date(2025, 5, 20)

    def it_should_return_float_for_amount_column(self):
        model = _make_model([make_group(amount=-99.99)])
        val = model.data(
            _index(model, 0, TransactionTableModel.COL_AMOUNT), TransactionTableModel.SortRole
        )
        assert val == -99.99

    def it_should_fall_back_to_display_value_for_description_column(self):
        model = _make_model([make_group(description="ACME CORP")])
        val = model.data(
            _index(model, 0, TransactionTableModel.COL_DESCRIPTION), TransactionTableModel.SortRole
        )
        assert val == "ACME CORP"


class DescribeTransactionTableModelTextAlignmentRole:
    """data() with TextAlignmentRole right-aligns amounts."""

    def it_should_right_align_amount_column(self):
        model = _make_model([make_group()])
        val = model.data(_index(model, 0, TransactionTableModel.COL_AMOUNT), Qt.TextAlignmentRole)
        assert val == (Qt.AlignRight | Qt.AlignVCenter)

    def it_should_not_align_description_column(self):
        model = _make_model([make_group()])
        val = model.data(
            _index(model, 0, TransactionTableModel.COL_DESCRIPTION), Qt.TextAlignmentRole
        )
        assert val is None


class DescribeTransactionTableModelForegroundRole:
    """data() with ForegroundRole colours amounts correctly."""

    def it_should_return_negative_color_for_debit_amount(self):
        model = _make_model([make_group(amount=-50.0)])
        with patch("gilt.gui.models.transaction_model.Theme") as mock_theme:
            mock_theme.color.return_value = "red_color"
            val = model.data(_index(model, 0, TransactionTableModel.COL_AMOUNT), Qt.ForegroundRole)
            mock_theme.color.assert_called_with("negative_fg")
            assert val == "red_color"

    def it_should_return_positive_color_for_credit_amount(self):
        model = _make_model([make_group(amount=100.0)])
        with patch("gilt.gui.models.transaction_model.Theme") as mock_theme:
            mock_theme.color.return_value = "green_color"
            val = model.data(_index(model, 0, TransactionTableModel.COL_AMOUNT), Qt.ForegroundRole)
            mock_theme.color.assert_called_with("positive_fg")
            assert val == "green_color"

    def it_should_return_neutral_color_for_zero_amount(self):
        model = _make_model([make_group(amount=0.0)])
        with patch("gilt.gui.models.transaction_model.Theme") as mock_theme:
            mock_theme.color.return_value = "gray_color"
            val = model.data(_index(model, 0, TransactionTableModel.COL_AMOUNT), Qt.ForegroundRole)
            mock_theme.color.assert_called_with("neutral_fg")
            assert val == "gray_color"

    def it_should_return_none_for_description_column_without_enrichment(self):
        model = _make_model([make_group()])
        val = model.data(_index(model, 0, TransactionTableModel.COL_DESCRIPTION), Qt.ForegroundRole)
        assert val is None


class DescribeTransactionTableModelSetData:
    """setData() parses category strings and updates the transaction."""

    def it_should_set_category_without_subcategory(self):
        group = make_group(category=None)
        model = _make_model([group])
        model.setData(_index(model, 0, TransactionTableModel.COL_CATEGORY), "Housing", Qt.EditRole)
        assert group.primary.category == "Housing"
        assert group.primary.subcategory is None

    def it_should_parse_category_colon_subcategory_format(self):
        group = make_group(category=None)
        model = _make_model([group])
        model.setData(
            _index(model, 0, TransactionTableModel.COL_CATEGORY), "Housing: Rent", Qt.EditRole
        )
        assert group.primary.category == "Housing"
        assert group.primary.subcategory == "Rent"

    def it_should_strip_whitespace_from_parsed_category_parts(self):
        group = make_group(category=None)
        model = _make_model([group])
        model.setData(
            _index(model, 0, TransactionTableModel.COL_CATEGORY),
            "  Housing :  Utilities  ",
            Qt.EditRole,
        )
        assert group.primary.category == "Housing"
        assert group.primary.subcategory == "Utilities"

    def it_should_return_false_for_non_edit_role(self):
        group = make_group()
        model = _make_model([group])
        result = model.setData(
            _index(model, 0, TransactionTableModel.COL_CATEGORY), "Housing", Qt.DisplayRole
        )
        assert result is False

    def it_should_return_false_for_non_category_column(self):
        group = make_group()
        model = _make_model([group])
        result = model.setData(
            _index(model, 0, TransactionTableModel.COL_DESCRIPTION), "new desc", Qt.EditRole
        )
        assert result is False

    def it_should_return_true_when_category_changes(self):
        group = make_group(category="Old")
        model = _make_model([group])
        result = model.setData(
            _index(model, 0, TransactionTableModel.COL_CATEGORY), "New", Qt.EditRole
        )
        assert result is True

    def it_should_return_false_when_category_unchanged(self):
        group = make_group(category="Housing", subcategory=None)
        model = _make_model([group])
        result = model.setData(
            _index(model, 0, TransactionTableModel.COL_CATEGORY), "Housing", Qt.EditRole
        )
        assert result is False
