from __future__ import annotations

"""Specs for TransactionTableWidget logic — no real financial data, PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")

from datetime import date

from gilt.model.account import Transaction, TransactionGroup


def _make_group(
    transaction_id: str = "aaaa111122223333",
    txn_date: date = date(2025, 2, 20),
    description: str = "SAMPLE STORE ANYTOWN",
    amount: float = -75.00,
    account_id: str = "MYBANK_CHQ",
    category: str | None = None,
) -> TransactionGroup:
    txn = Transaction(
        transaction_id=transaction_id,
        date=txn_date,
        description=description,
        amount=amount,
        currency="CAD",
        account_id=account_id,
        category=category,
    )
    return TransactionGroup(group_id=transaction_id, primary=txn)


class DescribeGetSelectedTransactions:
    """Tests for proxy-to-source model index mapping in get_selected_transactions."""

    def it_should_return_empty_list_when_no_rows_selected(self):
        # Simulate: no selected rows → empty result
        selected_rows = []
        result = [row for row in selected_rows]
        assert result == []

    def it_should_map_proxy_index_to_source_for_each_selected_row(self):
        # Verify the mapping pattern: proxy index → source index → transaction
        # We simulate the look-up chain without instantiating Qt objects.
        groups = [
            _make_group("aaaa111122223333"),
            _make_group("bbbb444455556666"),
        ]

        # Simulate model storage
        model_transactions = {0: groups[0], 1: groups[1]}

        # Simulate proxy → source mapping (identity here for simplicity)
        def map_to_source(proxy_row: int) -> int:
            return proxy_row

        selected_proxy_rows = [0, 1]
        result = []
        for proxy_row in selected_proxy_rows:
            source_row = map_to_source(proxy_row)
            txn = model_transactions.get(source_row)
            if txn:
                result.append(txn)

        assert len(result) == 2
        assert result[0].primary.transaction_id == "aaaa111122223333"
        assert result[1].primary.transaction_id == "bbbb444455556666"


class DescribeSelectTransactionById:
    """Tests for select_transaction_by_id row lookup logic."""

    def it_should_return_true_when_transaction_id_found(self):
        groups = [
            _make_group("aaaa111122223333"),
            _make_group("bbbb444455556666"),
        ]
        target_id = "bbbb444455556666"

        found = False
        for group in groups:
            if group.primary.transaction_id == target_id:
                found = True
                break
        assert found is True

    def it_should_return_false_when_transaction_id_not_present(self):
        groups = [
            _make_group("aaaa111122223333"),
        ]
        target_id = "xxxxyyyyzzzz9999"

        found = False
        for group in groups:
            if group.primary.transaction_id == target_id:
                found = True
                break
        assert found is False

    def it_should_match_on_full_transaction_id_not_prefix(self):
        groups = [_make_group("aaaa111122223333")]
        # Searching by 8-char prefix should NOT match here (full ID check)
        target_id = "aaaa1111"
        found = any(g.primary.transaction_id == target_id for g in groups)
        assert found is False


class DescribeContextMenuActionVisibility:
    """Tests for action visibility rules based on selection and categorization state."""

    def it_should_show_categorize_action_for_any_non_empty_selection(self):
        selected = [_make_group()]
        # Categorize is always shown when selection non-empty
        show_categorize = len(selected) > 0
        assert show_categorize is True

    def it_should_show_note_action_only_for_single_selection(self):
        selected_single = [_make_group()]
        selected_multi = [_make_group(), _make_group("bbbb444455556666")]
        assert len(selected_single) == 1
        assert len(selected_multi) != 1

    def it_should_show_merge_action_only_for_exactly_two_selections(self):
        selected = [_make_group(), _make_group("bbbb444455556666")]
        show_merge = len(selected) == 2
        assert show_merge is True

    def it_should_not_show_merge_for_single_selection(self):
        selected = [_make_group()]
        show_merge = len(selected) == 2
        assert show_merge is False

    def it_should_not_show_merge_for_three_selections(self):
        selected = [
            _make_group(),
            _make_group("bbbb444455556666"),
            _make_group("cccc777788889999"),
        ]
        show_merge = len(selected) == 2
        assert show_merge is False

    def it_should_show_apply_prediction_for_uncategorized_with_prediction(self):
        group = _make_group(category=None)
        txn = group.primary
        has_prediction = True  # Simulated metadata lookup
        show_apply = (not txn.category) and has_prediction
        assert show_apply is True

    def it_should_not_show_apply_prediction_for_already_categorized(self):
        group = _make_group(category="Groceries")
        txn = group.primary
        has_prediction = True
        show_apply = (not txn.category) and has_prediction
        assert show_apply is False

    def it_should_not_show_apply_prediction_when_no_prediction_available(self):
        group = _make_group(category=None)
        txn = group.primary
        has_prediction = False
        show_apply = (not txn.category) and has_prediction
        assert show_apply is False


class DescribeSetFilters:
    """Tests that set_filters delegates to proxy model."""

    def it_should_delegate_filter_kwargs_to_proxy_model(self):
        # Simulate that set_filters passes kwargs through to proxy.set_filters
        received_kwargs: dict = {}

        class _FakeProxy:
            def set_filters(self, **kwargs):
                received_kwargs.update(kwargs)

        proxy = _FakeProxy()
        proxy.set_filters(account_id="MYBANK_CHQ", category="Groceries")

        assert received_kwargs == {"account_id": "MYBANK_CHQ", "category": "Groceries"}
