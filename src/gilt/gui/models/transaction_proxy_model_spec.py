from __future__ import annotations

"""
Specifications for TransactionSortFilterProxyModel.
"""

import pytest

pytest.importorskip("PySide6")

from datetime import date

from PySide6.QtWidgets import QApplication

from gilt.gui.models.transaction_model import TransactionTableModel
from gilt.gui.models.transaction_proxy_model import TransactionSortFilterProxyModel
from gilt.model.account import Transaction, TransactionGroup

# ---------------------------------------------------------------------------
# QApplication singleton
# ---------------------------------------------------------------------------


def _get_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_txn(**kwargs) -> Transaction:
    defaults = dict(
        transaction_id="aabbccdd11223344",
        date=date(2025, 3, 10),
        description="SAMPLE STORE ANYTOWN",
        amount=-42.50,
        currency="CAD",
        account_id="MYBANK_CHQ",
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def _make_group(txn: Transaction | None = None, **kwargs) -> TransactionGroup:
    if txn is None:
        txn = _make_txn(**kwargs)
    return TransactionGroup(group_id=txn.transaction_id, primary=txn)


def _make_proxy_with_groups(groups: list[TransactionGroup]) -> TransactionSortFilterProxyModel:
    _get_app()
    source = TransactionTableModel()
    source.update_transactions(groups)
    proxy = TransactionSortFilterProxyModel()
    proxy.setSourceModel(source)
    return proxy


def _all_visible_account_ids(proxy: TransactionSortFilterProxyModel) -> list[str]:
    return [
        proxy.sourceModel()
            .get_transaction(proxy.mapToSource(proxy.index(r, 0)).row())
            .primary.account_id
        for r in range(proxy.rowCount())
    ]


def _all_visible_transactions(proxy: TransactionSortFilterProxyModel) -> list[Transaction]:
    return [
        proxy.sourceModel()
            .get_transaction(proxy.mapToSource(proxy.index(r, 0)).row())
            .primary
        for r in range(proxy.rowCount())
    ]


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------


class DescribeTransactionSortFilterProxyModelSetFilters:
    """set_filters() updates internal state and triggers re-filtering."""

    def it_should_show_all_rows_with_no_filters(self):
        groups = [
            _make_group(transaction_id="id01" + "0" * 12, account_id="MYBANK_CHQ"),
            _make_group(transaction_id="id02" + "0" * 12, account_id="BANK2_BIZ"),
        ]
        proxy = _make_proxy_with_groups(groups)
        proxy.set_filters()
        assert proxy.rowCount() == 2

    def it_should_store_account_filter(self):
        proxy = _make_proxy_with_groups([])
        proxy.set_filters(account_filter=["MYBANK_CHQ"])
        assert proxy._account_filter == ["MYBANK_CHQ"]

    def it_should_lowercase_search_text(self):
        proxy = _make_proxy_with_groups([])
        proxy.set_filters(search_text="ACME")
        assert proxy._search_text == "acme"

    def it_should_set_search_text_to_none_when_empty(self):
        proxy = _make_proxy_with_groups([])
        proxy.set_filters(search_text="")
        assert proxy._search_text is None


class DescribeTransactionSortFilterProxyModelFilterAcceptsRow:
    """filterAcceptsRow() applies all active filter criteria."""

    def it_should_accept_row_matching_account_filter(self):
        groups = [
            _make_group(transaction_id="chq0" + "0" * 12, account_id="MYBANK_CHQ"),
            _make_group(transaction_id="biz0" + "0" * 12, account_id="BANK2_BIZ"),
        ]
        proxy = _make_proxy_with_groups(groups)
        proxy.set_filters(account_filter=["MYBANK_CHQ"])
        visible = _all_visible_account_ids(proxy)
        assert visible == ["MYBANK_CHQ"]

    def it_should_reject_row_not_in_account_filter(self):
        groups = [
            _make_group(transaction_id="chq0" + "0" * 12, account_id="MYBANK_CHQ"),
            _make_group(transaction_id="biz0" + "0" * 12, account_id="BANK2_BIZ"),
        ]
        proxy = _make_proxy_with_groups(groups)
        proxy.set_filters(account_filter=["MYBANK_CC"])
        assert proxy.rowCount() == 0

    def it_should_filter_by_start_date(self):
        groups = [
            _make_group(
                transaction_id="old0" + "0" * 12,
                date=date(2024, 12, 31),
                account_id="MYBANK_CHQ",
            ),
            _make_group(
                transaction_id="new0" + "0" * 12,
                date=date(2025, 1, 15),
                account_id="MYBANK_CHQ",
            ),
        ]
        proxy = _make_proxy_with_groups(groups)
        proxy.set_filters(start_date=date(2025, 1, 1))
        visible = _all_visible_transactions(proxy)
        assert len(visible) == 1
        assert visible[0].date == date(2025, 1, 15)

    def it_should_filter_by_end_date(self):
        groups = [
            _make_group(
                transaction_id="old0" + "0" * 12,
                date=date(2024, 12, 31),
                account_id="MYBANK_CHQ",
            ),
            _make_group(
                transaction_id="new0" + "0" * 12,
                date=date(2025, 2, 1),
                account_id="MYBANK_CHQ",
            ),
        ]
        proxy = _make_proxy_with_groups(groups)
        proxy.set_filters(end_date=date(2025, 1, 1))
        visible = _all_visible_transactions(proxy)
        assert len(visible) == 1
        assert visible[0].date == date(2024, 12, 31)

    def it_should_filter_by_category(self):
        groups = [
            _make_group(
                transaction_id="cat0" + "0" * 12,
                account_id="MYBANK_CHQ",
                category="Housing",
            ),
            _make_group(
                transaction_id="cat1" + "0" * 12,
                account_id="MYBANK_CHQ",
                category="Transportation",
            ),
        ]
        proxy = _make_proxy_with_groups(groups)
        proxy.set_filters(category_filter=["Housing"])
        visible = _all_visible_transactions(proxy)
        assert len(visible) == 1
        assert visible[0].category == "Housing"

    def it_should_filter_uncategorized_only(self):
        groups = [
            _make_group(
                transaction_id="cat0" + "0" * 12,
                account_id="MYBANK_CHQ",
                category="Housing",
            ),
            _make_group(
                transaction_id="unc0" + "0" * 12,
                account_id="MYBANK_CHQ",
                category=None,
            ),
        ]
        proxy = _make_proxy_with_groups(groups)
        proxy.set_filters(uncategorized_only=True)
        visible = _all_visible_transactions(proxy)
        assert len(visible) == 1
        assert visible[0].category is None

    def it_should_filter_by_search_text_case_insensitively(self):
        groups = [
            _make_group(
                transaction_id="s001" + "0" * 12,
                account_id="MYBANK_CHQ",
                description="ACME CORP PURCHASE",
            ),
            _make_group(
                transaction_id="s002" + "0" * 12,
                account_id="MYBANK_CHQ",
                description="EXAMPLE UTILITY",
            ),
        ]
        proxy = _make_proxy_with_groups(groups)
        proxy.set_filters(search_text="acme")
        visible = _all_visible_transactions(proxy)
        assert len(visible) == 1
        assert "ACME" in visible[0].description

    def it_should_apply_multiple_filters_conjunctively(self):
        groups = [
            _make_group(
                transaction_id="m001" + "0" * 12,
                account_id="MYBANK_CHQ",
                description="ACME CORP",
                date=date(2025, 1, 10),
            ),
            _make_group(
                transaction_id="m002" + "0" * 12,
                account_id="BANK2_BIZ",
                description="ACME CORP",
                date=date(2025, 1, 10),
            ),
        ]
        proxy = _make_proxy_with_groups(groups)
        proxy.set_filters(
            account_filter=["MYBANK_CHQ"],
            search_text="acme",
        )
        visible = _all_visible_transactions(proxy)
        assert len(visible) == 1
        assert visible[0].account_id == "MYBANK_CHQ"


class DescribeTransactionSortFilterProxyModelLessThan:
    """lessThan() compares rows correctly for various column types."""

    def it_should_sort_by_amount_numerically(self):
        groups = [
            _make_group(transaction_id="a001" + "0" * 12, account_id="MYBANK_CHQ", amount=-200.0),
            _make_group(transaction_id="a002" + "0" * 12, account_id="MYBANK_CHQ", amount=-50.0),
        ]
        proxy = _make_proxy_with_groups(groups)
        proxy.sort(TransactionTableModel.COL_AMOUNT, TransactionTableModel.SortRole)
        visible = _all_visible_transactions(proxy)
        # After ascending sort, -200 should come before -50
        assert visible[0].amount < visible[1].amount

    def it_should_sort_by_date_chronologically(self):
        groups = [
            _make_group(
                transaction_id="d001" + "0" * 12,
                account_id="MYBANK_CHQ",
                date=date(2025, 6, 1),
            ),
            _make_group(
                transaction_id="d002" + "0" * 12,
                account_id="MYBANK_CHQ",
                date=date(2025, 1, 1),
            ),
        ]
        proxy = _make_proxy_with_groups(groups)
        from PySide6.QtCore import Qt as QtCore
        proxy.sort(TransactionTableModel.COL_DATE, QtCore.AscendingOrder)
        visible = _all_visible_transactions(proxy)
        assert visible[0].date < visible[1].date

    def it_should_sort_by_description_alphabetically(self):
        groups = [
            _make_group(
                transaction_id="desc01" + "0" * 10,
                account_id="MYBANK_CHQ",
                description="ZETA CORP",
            ),
            _make_group(
                transaction_id="desc02" + "0" * 10,
                account_id="MYBANK_CHQ",
                description="ALPHA STORE",
            ),
        ]
        proxy = _make_proxy_with_groups(groups)
        from PySide6.QtCore import Qt as QtCore
        proxy.sort(TransactionTableModel.COL_DESCRIPTION, QtCore.AscendingOrder)
        visible = _all_visible_transactions(proxy)
        assert visible[0].description < visible[1].description
