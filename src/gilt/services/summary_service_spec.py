from __future__ import annotations

"""
Tests for summary_service — category/subcategory aggregation.
"""

from datetime import date

from gilt.model.account import Transaction
from gilt.services.summary_service import (
    build_category_summary,
    build_subcategory_summary,
)


def _txn(
    txn_id: str,
    amount: float,
    category: str | None = None,
    subcategory: str | None = None,
    txn_date: str = "2026-01-15",
) -> Transaction:
    return Transaction(
        transaction_id=txn_id,
        date=date.fromisoformat(txn_date),
        description="SAMPLE STORE",
        amount=amount,
        currency="CAD",
        account_id="MYBANK_CHQ",
        category=category,
        subcategory=subcategory,
    )


class DescribeBuildCategorySummary:
    def it_should_aggregate_counts_and_nets_per_category(self):
        txns = [
            _txn("1111111111111111", -100.0, "Housing"),
            _txn("2222222222222222", -200.0, "Housing"),
            _txn("3333333333333333", -50.0, "Food"),
        ]
        rows = build_category_summary(txns, include_uncategorized=False)
        categories = {r.category: r for r in rows}

        assert categories["Housing"].count == 2
        assert categories["Housing"].net == -300.0
        assert categories["Food"].count == 1
        assert categories["Food"].net == -50.0

    def it_should_sort_by_abs_net_descending(self):
        txns = [
            _txn("1111111111111111", -50.0, "Food"),
            _txn("2222222222222222", -300.0, "Housing"),
            _txn("3333333333333333", 200.0, "Work"),
        ]
        rows = build_category_summary(txns, include_uncategorized=False)
        assert rows[0].category == "Housing"  # abs 300
        assert rows[1].category == "Work"  # abs 200
        assert rows[2].category == "Food"  # abs 50

    def it_should_sort_by_category_name_as_tiebreaker(self):
        txns = [
            _txn("1111111111111111", -100.0, "Zeta"),
            _txn("2222222222222222", -100.0, "Alpha"),
        ]
        rows = build_category_summary(txns, include_uncategorized=False)
        assert rows[0].category == "Alpha"
        assert rows[1].category == "Zeta"

    def it_should_exclude_uncategorized_when_flag_is_false(self):
        txns = [
            _txn("1111111111111111", -100.0, "Housing"),
            _txn("2222222222222222", -200.0, None),
            _txn("3333333333333333", -50.0, ""),
        ]
        rows = build_category_summary(txns, include_uncategorized=False)
        assert len(rows) == 1
        assert rows[0].category == "Housing"

    def it_should_include_uncategorized_when_flag_is_true(self):
        txns = [
            _txn("1111111111111111", -100.0, "Housing"),
            _txn("2222222222222222", -200.0, None),
            _txn("3333333333333333", -50.0, ""),
        ]
        rows = build_category_summary(txns, include_uncategorized=True)
        categories = {r.category: r for r in rows}

        assert None in categories
        assert categories[None].count == 2
        assert categories[None].net == -250.0

    def it_should_return_empty_list_for_no_transactions(self):
        rows = build_category_summary([], include_uncategorized=False)
        assert rows == []

    def it_should_handle_mixed_positive_and_negative(self):
        txns = [
            _txn("1111111111111111", -500.0, "Housing"),
            _txn("2222222222222222", 200.0, "Housing"),
        ]
        rows = build_category_summary(txns, include_uncategorized=False)
        assert len(rows) == 1
        assert rows[0].net == -300.0
        assert rows[0].count == 2


class DescribeBuildSubcategorySummary:
    def it_should_filter_to_matching_category(self):
        txns = [
            _txn("1111111111111111", -100.0, "Housing", "Rent"),
            _txn("2222222222222222", -50.0, "Food", "Groceries"),
        ]
        total, rows = build_subcategory_summary(txns, "Housing")
        assert len(rows) == 1
        assert rows[0].subcategory == "Rent"

    def it_should_bucket_none_subcategory_under_none_key(self):
        txns = [
            _txn("1111111111111111", -100.0, "Housing", None),
            _txn("2222222222222222", -50.0, "Housing", ""),
            _txn("3333333333333333", -200.0, "Housing", "Rent"),
        ]
        total, rows = build_subcategory_summary(txns, "Housing")
        subcats = {r.subcategory: r for r in rows}

        assert None in subcats
        assert subcats[None].count == 2
        assert subcats[None].net == -150.0

    def it_should_compute_pct_of_category(self):
        txns = [
            _txn("1111111111111111", -300.0, "Housing", "Rent"),
            _txn("2222222222222222", -100.0, "Housing", "Utilities"),
        ]
        total, rows = build_subcategory_summary(txns, "Housing")
        assert total == -400.0
        subcats = {r.subcategory: r for r in rows}
        assert subcats["Rent"].pct_of_category == 75.0
        assert subcats["Utilities"].pct_of_category == 25.0

    def it_should_return_zero_pct_when_category_total_is_zero(self):
        txns = [
            _txn("1111111111111111", 100.0, "Housing", "Refund"),
            _txn("2222222222222222", -100.0, "Housing", "Rent"),
        ]
        total, rows = build_subcategory_summary(txns, "Housing")
        assert total == 0.0
        for row in rows:
            assert row.pct_of_category == 0.0

    def it_should_sort_rows_by_abs_net_descending(self):
        txns = [
            _txn("1111111111111111", -50.0, "Housing", "Utilities"),
            _txn("2222222222222222", -300.0, "Housing", "Rent"),
        ]
        _total, rows = build_subcategory_summary(txns, "Housing")
        assert rows[0].subcategory == "Rent"
        assert rows[1].subcategory == "Utilities"

    def it_should_return_empty_rows_for_unknown_category(self):
        txns = [
            _txn("1111111111111111", -100.0, "Housing", "Rent"),
        ]
        total, rows = build_subcategory_summary(txns, "NonExistent")
        assert total == 0.0
        assert rows == []
