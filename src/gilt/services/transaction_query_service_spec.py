from __future__ import annotations

"""
Specs for TransactionQueryService - pure filtering and aggregation logic.

All tests use Transaction objects directly — no projections DB, no file I/O.
"""

from gilt.services.transaction_query_service import (
    TransactionFilter,
    TransactionQueryService,
    TransactionTotals,
)
from gilt.testing.fixtures import make_transaction
from gilt.transfer import (
    ROLE_CREDIT,
    ROLE_DEBIT,
    TRANSFER_COUNTERPARTY_ACCOUNT_ID,
    TRANSFER_META_KEY,
    TRANSFER_ROLE,
)


class DescribeFilterTransactions:
    def it_should_filter_by_account_id(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", account_id="MYBANK_CHQ"),
            make_transaction(transaction_id="t2", account_id="MYBANK_CC"),
            make_transaction(transaction_id="t3", account_id="MYBANK_CHQ"),
        ]
        result = service.find_transactions(
            transactions, account_id="MYBANK_CHQ", year=None, limit=None
        )
        assert len(result) == 2
        assert all(t.account_id == "MYBANK_CHQ" for t in result)

    def it_should_filter_by_year(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", date="2025-03-15", account_id="MYBANK_CHQ"),
            make_transaction(transaction_id="t2", date="2024-03-15", account_id="MYBANK_CHQ"),
            make_transaction(transaction_id="t3", date="2025-11-01", account_id="MYBANK_CHQ"),
        ]
        result = service.find_transactions(
            transactions, account_id="MYBANK_CHQ", year=2025, limit=None
        )
        assert len(result) == 2
        assert all(t.date.year == 2025 for t in result)

    def it_should_sort_by_date_then_transaction_id(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(
                transaction_id="zzzzzzzzzzzzzzzz",
                date="2025-10-05",
                account_id="MYBANK_CHQ",
            ),
            make_transaction(
                transaction_id="aaaaaaaaaaaaaaaa",
                date="2025-10-05",
                account_id="MYBANK_CHQ",
            ),
            make_transaction(
                transaction_id="mmmmmmmmmmmmmmmm",
                date="2025-10-01",
                account_id="MYBANK_CHQ",
            ),
        ]
        result = service.find_transactions(
            transactions, account_id="MYBANK_CHQ", year=None, limit=None
        )
        assert result[0].transaction_id == "mmmmmmmmmmmmmmmm"
        assert result[1].transaction_id == "aaaaaaaaaaaaaaaa"
        assert result[2].transaction_id == "zzzzzzzzzzzzzzzz"

    def it_should_apply_limit(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(
                transaction_id=f"t{i:016d}", date="2025-10-01", account_id="MYBANK_CHQ"
            )
            for i in range(5)
        ]
        result = service.find_transactions(
            transactions, account_id="MYBANK_CHQ", year=None, limit=3
        )
        assert len(result) == 3

    def it_should_return_empty_list_for_no_matches(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", account_id="MYBANK_CC"),
        ]
        result = service.find_transactions(
            transactions, account_id="MYBANK_CHQ", year=None, limit=None
        )
        assert result == []


class DescribeCalculateTotals:
    def it_should_calculate_credits_debits_and_net(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", amount=500.00),  # credit
            make_transaction(transaction_id="t2", amount=-100.00),  # debit
            make_transaction(transaction_id="t3", amount=-50.00),  # debit
        ]
        totals = service.get_totals(transactions)
        assert totals.credits == 500.00
        assert totals.debits == -150.00
        assert abs(totals.net - 350.00) < 0.001

    def it_should_handle_empty_list(self):
        service = TransactionQueryService()
        totals = service.get_totals([])
        assert isinstance(totals, TransactionTotals)
        assert totals.credits == 0.0
        assert totals.debits == 0.0
        assert totals.net == 0.0


class DescribeBuildDisplayNotes:
    def it_should_include_category_with_subcategory(self):
        service = TransactionQueryService()
        txn = make_transaction(category="Groceries", subcategory="Produce")
        notes = service.build_display_notes(txn)
        assert "Groceries:Produce" in notes

    def it_should_include_category_without_subcategory(self):
        service = TransactionQueryService()
        txn = make_transaction(category="Groceries", subcategory=None)
        notes = service.build_display_notes(txn)
        assert "Groceries" in notes
        assert ":" not in notes

    def it_should_include_transfer_info(self):
        service = TransactionQueryService()
        txn = make_transaction(
            metadata={
                TRANSFER_META_KEY: {
                    TRANSFER_ROLE: ROLE_DEBIT,
                    TRANSFER_COUNTERPARTY_ACCOUNT_ID: "MYBANK_SAV",
                }
            }
        )
        notes = service.build_display_notes(txn)
        assert "Transfer to MYBANK_SAV" in notes

    def it_should_include_transfer_from_for_credit_role(self):
        service = TransactionQueryService()
        txn = make_transaction(
            metadata={
                TRANSFER_META_KEY: {
                    TRANSFER_ROLE: ROLE_CREDIT,
                    TRANSFER_COUNTERPARTY_ACCOUNT_ID: "MYBANK_CHQ",
                }
            }
        )
        notes = service.build_display_notes(txn)
        assert "Transfer from MYBANK_CHQ" in notes

    def it_should_include_user_notes(self):
        service = TransactionQueryService()
        txn = make_transaction(notes="Paid by cheque")
        notes = service.build_display_notes(txn)
        assert "Paid by cheque" in notes

    def it_should_combine_multiple_note_parts_with_pipe_separator(self):
        service = TransactionQueryService()
        txn = make_transaction(category="Utilities", notes="Monthly bill")
        notes = service.build_display_notes(txn)
        assert " | " in notes
        assert "Utilities" in notes
        assert "Monthly bill" in notes

    def it_should_return_empty_string_when_no_notes(self):
        service = TransactionQueryService()
        txn = make_transaction(category=None, notes=None)
        notes = service.build_display_notes(txn)
        assert notes == ""


class DescribeFindMatching:
    """Specs for TransactionQueryService.find_matching — pure predicate filtering."""

    def it_should_return_all_transactions_when_no_criteria(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", account_id="MYBANK_CHQ"),
            make_transaction(transaction_id="t2", account_id="MYBANK_CC"),
        ]

        result = service.find_matching(transactions, TransactionFilter())

        assert len(result) == 2

    def it_should_filter_by_account_id(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", account_id="MYBANK_CHQ"),
            make_transaction(transaction_id="t2", account_id="MYBANK_CC"),
            make_transaction(transaction_id="t3", account_id="MYBANK_CHQ"),
        ]

        result = service.find_matching(transactions, TransactionFilter(account_id="MYBANK_CHQ"))

        assert len(result) == 2
        assert all(t.account_id == "MYBANK_CHQ" for t in result)

    def it_should_filter_by_exact_year(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", date="2025-03-15"),
            make_transaction(transaction_id="t2", date="2024-06-10"),
            make_transaction(transaction_id="t3", date="2025-11-01"),
        ]

        result = service.find_matching(transactions, TransactionFilter(year=2025))

        assert len(result) == 2
        assert all(t.date.year == 2025 for t in result)

    def it_should_include_fy_range_boundary_start(self):
        from datetime import date as d

        service = TransactionQueryService()
        boundary_start = make_transaction(transaction_id="t1", date="2024-11-01")
        before_start = make_transaction(transaction_id="t2", date="2024-10-31")
        fy_range = (d(2024, 11, 1), d(2025, 10, 31))

        result = service.find_matching(transactions=[boundary_start, before_start],
                                       criteria=TransactionFilter(fy_range=fy_range))

        assert len(result) == 1
        assert result[0].transaction_id == "t1"

    def it_should_include_fy_range_boundary_end(self):
        from datetime import date as d

        service = TransactionQueryService()
        boundary_end = make_transaction(transaction_id="t1", date="2025-10-31")
        after_end = make_transaction(transaction_id="t2", date="2025-11-01")
        fy_range = (d(2024, 11, 1), d(2025, 10, 31))

        result = service.find_matching(transactions=[boundary_end, after_end],
                                       criteria=TransactionFilter(fy_range=fy_range))

        assert len(result) == 1
        assert result[0].transaction_id == "t1"

    def it_should_match_amount_eq_within_tolerance(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", amount=-100.00),
            make_transaction(transaction_id="t2", amount=-100.009),  # within 0.01
            make_transaction(transaction_id="t3", amount=-100.02),   # outside 0.01
            make_transaction(transaction_id="t4", amount=-50.00),
        ]

        result = service.find_matching(transactions, TransactionFilter(amount_eq=-100.00))

        ids = {t.transaction_id for t in result}
        assert "t1" in ids
        assert "t2" in ids
        assert "t3" not in ids
        assert "t4" not in ids

    def it_should_apply_amount_min_signed_bound(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", amount=-50.00),
            make_transaction(transaction_id="t2", amount=-200.00),
            make_transaction(transaction_id="t3", amount=100.00),
        ]

        result = service.find_matching(transactions, TransactionFilter(amount_min=-100.00))

        ids = {t.transaction_id for t in result}
        assert "t1" in ids   # -50 >= -100
        assert "t3" in ids   # 100 >= -100
        assert "t2" not in ids  # -200 < -100

    def it_should_apply_amount_max_signed_bound(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", amount=-50.00),
            make_transaction(transaction_id="t2", amount=200.00),
            make_transaction(transaction_id="t3", amount=100.00),
        ]

        result = service.find_matching(transactions, TransactionFilter(amount_max=100.00))

        ids = {t.transaction_id for t in result}
        assert "t1" in ids    # -50 <= 100
        assert "t3" in ids    # 100 <= 100
        assert "t2" not in ids   # 200 > 100

    def it_should_apply_min_abs_amount_filter(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", amount=-10.00),
            make_transaction(transaction_id="t2", amount=-500.00),
            make_transaction(transaction_id="t3", amount=250.00),
        ]

        result = service.find_matching(transactions, TransactionFilter(min_abs_amount=100.00))

        ids = {t.transaction_id for t in result}
        assert "t2" in ids   # abs(-500) = 500 >= 100
        assert "t3" in ids   # abs(250) = 250 >= 100
        assert "t1" not in ids  # abs(-10) = 10 < 100

    def it_should_filter_by_category_case_insensitive(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", category="Groceries"),
            make_transaction(transaction_id="t2", category="utilities"),
            make_transaction(transaction_id="t3", category="Groceries"),
            make_transaction(transaction_id="t4", category=None),
        ]

        result = service.find_matching(transactions, TransactionFilter(category="groceries"))

        ids = {t.transaction_id for t in result}
        assert "t1" in ids
        assert "t3" in ids
        assert "t2" not in ids
        assert "t4" not in ids

    def it_should_filter_by_subcategory_case_insensitive(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(transaction_id="t1", category="Housing", subcategory="Rent"),
            make_transaction(transaction_id="t2", category="Housing", subcategory="Utilities"),
            make_transaction(transaction_id="t3", category="Housing", subcategory=None),
        ]

        result = service.find_matching(transactions, TransactionFilter(subcategory="rent"))

        assert len(result) == 1
        assert result[0].transaction_id == "t1"

    def it_should_apply_multiple_criteria_as_and(self):
        service = TransactionQueryService()
        transactions = [
            make_transaction(
                transaction_id="t1", account_id="MYBANK_CHQ", date="2025-06-01", amount=-150.00
            ),
            make_transaction(
                transaction_id="t2", account_id="MYBANK_CC", date="2025-06-01", amount=-150.00
            ),
            make_transaction(
                transaction_id="t3", account_id="MYBANK_CHQ", date="2024-06-01", amount=-150.00
            ),
            make_transaction(
                transaction_id="t4", account_id="MYBANK_CHQ", date="2025-06-01", amount=-50.00
            ),
        ]

        result = service.find_matching(
            transactions,
            TransactionFilter(account_id="MYBANK_CHQ", year=2025, amount_min=-200.00,
                              amount_max=-100.00),
        )

        assert len(result) == 1
        assert result[0].transaction_id == "t1"
