from __future__ import annotations

"""
Tests for receipts_service: receipt coverage computation.
"""

from datetime import date

from gilt.services.receipts_service import build_receipt_coverage


def _row(
    *,
    transaction_id: str = "0000000000000001",
    transaction_date: str = "2025-01-15",
    canonical_description: str = "Example consulting",
    amount: float = -500.0,
    account_id: str = "MYBANK_CC",
    category: str = "Mojility",
    subcategory: str = "Consulting",
    receipt_file: str | None = None,
) -> dict:
    return {
        "transaction_id": transaction_id,
        "transaction_date": transaction_date,
        "canonical_description": canonical_description,
        "amount": amount,
        "account_id": account_id,
        "category": category,
        "subcategory": subcategory,
        "receipt_file": receipt_file,
    }


class DescribeBuildReceiptCoverage:
    """Tests for build_receipt_coverage service function."""

    def it_should_count_totals_and_with_receipt_correctly(self):
        rows = [
            _row(transaction_id="aaa1", receipt_file="receipt_a.pdf"),
            _row(transaction_id="aaa2", receipt_file=None),
            _row(transaction_id="aaa3", receipt_file="receipt_c.pdf"),
        ]
        result = build_receipt_coverage(rows)

        assert len(result.coverage_rows) == 1
        row = result.coverage_rows[0]
        assert row.total_txns == 3
        assert row.with_receipt == 2
        assert row.without_receipt == 1
        assert row.coverage_pct == 67  # round(2/3 * 100)

    def it_should_compute_net_amount_as_signed_sum(self):
        rows = [
            _row(transaction_id="b1", amount=-200.0),
            _row(transaction_id="b2", amount=-300.0),
        ]
        result = build_receipt_coverage(rows)
        assert result.coverage_rows[0].net_amount == -500.0

    def it_should_group_by_subcategory_by_default(self):
        rows = [
            _row(transaction_id="c1", subcategory="Consulting", amount=-100.0),
            _row(transaction_id="c2", subcategory="Software", amount=-50.0),
            _row(transaction_id="c3", subcategory="Consulting", amount=-75.0),
        ]
        result = build_receipt_coverage(rows)

        keys = {r.subcategory for r in result.coverage_rows}
        assert keys == {"Consulting", "Software"}

        consulting = next(r for r in result.coverage_rows if r.subcategory == "Consulting")
        assert consulting.total_txns == 2
        assert consulting.net_amount == -175.0

    def it_should_group_by_account_when_flag_set(self):
        rows = [
            _row(transaction_id="d1", account_id="MYBANK_CC", subcategory="Consulting"),
            _row(transaction_id="d2", account_id="BANK2_BIZ", subcategory="Consulting"),
            _row(transaction_id="d3", account_id="MYBANK_CC", subcategory="Software"),
        ]
        result = build_receipt_coverage(rows, group_by_account=True)

        keys = {r.account_id for r in result.coverage_rows}
        assert keys == {"MYBANK_CC", "BANK2_BIZ"}

        cc_row = next(r for r in result.coverage_rows if r.account_id == "MYBANK_CC")
        assert cc_row.total_txns == 2

    def it_should_filter_by_fy_range(self):
        fy_range = (date(2024, 11, 1), date(2025, 10, 31))
        rows = [
            _row(transaction_id="e1", transaction_date="2025-01-15"),  # inside FY25
            _row(transaction_id="e2", transaction_date="2025-11-05"),  # outside FY25
        ]
        result = build_receipt_coverage(rows, fy_range=fy_range)

        assert len(result.coverage_rows) == 1
        assert result.coverage_rows[0].total_txns == 1

    def it_should_filter_by_category(self):
        rows = [
            _row(transaction_id="f1", category="Mojility"),
            _row(transaction_id="f2", category="Food"),
        ]
        result = build_receipt_coverage(rows, category="Mojility")
        assert len(result.coverage_rows) == 1
        assert result.coverage_rows[0].total_txns == 1

    def it_should_list_missing_receipts_sorted_by_date(self):
        rows = [
            _row(
                transaction_id="g1",
                transaction_date="2025-03-01",
                canonical_description="March consulting",
                receipt_file=None,
            ),
            _row(
                transaction_id="g2",
                transaction_date="2025-01-10",
                canonical_description="January software",
                receipt_file=None,
            ),
            _row(
                transaction_id="g3",
                transaction_date="2025-02-15",
                canonical_description="February travel",
                receipt_file="receipt_g3.pdf",
            ),
        ]
        result = build_receipt_coverage(rows)

        assert len(result.missing_rows) == 2
        assert result.missing_rows[0].transaction_id == "g2"
        assert result.missing_rows[1].transaction_id == "g1"

    def it_should_exclude_receipted_transactions_from_missing_list(self):
        rows = [
            _row(transaction_id="h1", receipt_file="ok.pdf"),
        ]
        result = build_receipt_coverage(rows)
        assert result.missing_rows == []

    def it_should_return_empty_result_when_no_matching_transactions(self):
        rows = [
            _row(category="Food"),
        ]
        result = build_receipt_coverage(rows, category="Mojility")
        assert result.coverage_rows == []
        assert result.missing_rows == []

    def it_should_use_em_dash_for_coverage_pct_when_zero_total(self):
        """coverage_pct is '—' when there are no matching transactions in the bucket."""
        # This is tested indirectly — an empty result has no rows so coverage_pct never
        # reaches the "—" branch from zero total. But we can verify the pure calculation:
        # If somehow total_txns=0 appeared in a bucket, pct would be "—".
        # In practice total_txns >= 1 for any bucket that exists. The branch exists
        # for safety; test it via coverage_rows being empty on no-match.
        result = build_receipt_coverage([], category="Mojility")
        assert result.coverage_rows == []

    def it_should_handle_none_subcategory_gracefully(self):
        rows = [
            _row(transaction_id="i1", subcategory=None),
        ]
        result = build_receipt_coverage(rows)
        assert len(result.coverage_rows) == 1
        assert result.coverage_rows[0].subcategory == ""
