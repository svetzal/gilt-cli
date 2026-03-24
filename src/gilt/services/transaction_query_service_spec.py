from __future__ import annotations

"""
Specs for TransactionQueryService - pure filtering and aggregation logic.

All tests use Transaction objects directly — no projections DB, no file I/O.
"""

from gilt.model.account import Transaction
from gilt.services.transaction_query_service import (
    TransactionQueryService,
    TransactionTotals,
)
from gilt.transfer import (
    ROLE_CREDIT,
    ROLE_DEBIT,
    TRANSFER_COUNTERPARTY_ACCOUNT_ID,
    TRANSFER_META_KEY,
    TRANSFER_ROLE,
)


def _make_transaction(
    *,
    transaction_id: str = "abcd1234abcd1234",
    txn_date: str = "2025-10-01",
    description: str = "EXAMPLE UTILITY",
    amount: float = -100.00,
    currency: str = "CAD",
    account_id: str = "MYBANK_CHQ",
    category: str | None = None,
    subcategory: str | None = None,
    notes: str | None = None,
    metadata: dict | None = None,
) -> Transaction:
    return Transaction(
        transaction_id=transaction_id,
        date=txn_date,
        description=description,
        amount=amount,
        currency=currency,
        account_id=account_id,
        category=category,
        subcategory=subcategory,
        notes=notes,
        metadata=metadata or {},
    )


class DescribeFilterTransactions:
    def it_should_filter_by_account_id(self):
        service = TransactionQueryService()
        transactions = [
            _make_transaction(transaction_id="t1", account_id="MYBANK_CHQ"),
            _make_transaction(transaction_id="t2", account_id="MYBANK_CC"),
            _make_transaction(transaction_id="t3", account_id="MYBANK_CHQ"),
        ]
        result = service.filter_transactions(
            transactions, account_id="MYBANK_CHQ", year=None, limit=None
        )
        assert len(result) == 2
        assert all(t.account_id == "MYBANK_CHQ" for t in result)

    def it_should_filter_by_year(self):
        service = TransactionQueryService()
        transactions = [
            _make_transaction(transaction_id="t1", txn_date="2025-03-15", account_id="MYBANK_CHQ"),
            _make_transaction(transaction_id="t2", txn_date="2024-03-15", account_id="MYBANK_CHQ"),
            _make_transaction(transaction_id="t3", txn_date="2025-11-01", account_id="MYBANK_CHQ"),
        ]
        result = service.filter_transactions(
            transactions, account_id="MYBANK_CHQ", year=2025, limit=None
        )
        assert len(result) == 2
        assert all(t.date.year == 2025 for t in result)

    def it_should_sort_by_date_then_transaction_id(self):
        service = TransactionQueryService()
        transactions = [
            _make_transaction(
                transaction_id="zzzzzzzzzzzzzzzz",
                txn_date="2025-10-05",
                account_id="MYBANK_CHQ",
            ),
            _make_transaction(
                transaction_id="aaaaaaaaaaaaaaaa",
                txn_date="2025-10-05",
                account_id="MYBANK_CHQ",
            ),
            _make_transaction(
                transaction_id="mmmmmmmmmmmmmmmm",
                txn_date="2025-10-01",
                account_id="MYBANK_CHQ",
            ),
        ]
        result = service.filter_transactions(
            transactions, account_id="MYBANK_CHQ", year=None, limit=None
        )
        assert result[0].transaction_id == "mmmmmmmmmmmmmmmm"
        assert result[1].transaction_id == "aaaaaaaaaaaaaaaa"
        assert result[2].transaction_id == "zzzzzzzzzzzzzzzz"

    def it_should_apply_limit(self):
        service = TransactionQueryService()
        transactions = [
            _make_transaction(
                transaction_id=f"t{i:016d}", txn_date="2025-10-01", account_id="MYBANK_CHQ"
            )
            for i in range(5)
        ]
        result = service.filter_transactions(
            transactions, account_id="MYBANK_CHQ", year=None, limit=3
        )
        assert len(result) == 3

    def it_should_return_empty_list_for_no_matches(self):
        service = TransactionQueryService()
        transactions = [
            _make_transaction(transaction_id="t1", account_id="MYBANK_CC"),
        ]
        result = service.filter_transactions(
            transactions, account_id="MYBANK_CHQ", year=None, limit=None
        )
        assert result == []


class DescribeCalculateTotals:
    def it_should_calculate_credits_debits_and_net(self):
        service = TransactionQueryService()
        transactions = [
            _make_transaction(transaction_id="t1", amount=500.00),  # credit
            _make_transaction(transaction_id="t2", amount=-100.00),  # debit
            _make_transaction(transaction_id="t3", amount=-50.00),  # debit
        ]
        totals = service.calculate_totals(transactions)
        assert totals.credits == 500.00
        assert totals.debits == -150.00
        assert abs(totals.net - 350.00) < 0.001

    def it_should_handle_empty_list(self):
        service = TransactionQueryService()
        totals = service.calculate_totals([])
        assert isinstance(totals, TransactionTotals)
        assert totals.credits == 0.0
        assert totals.debits == 0.0
        assert totals.net == 0.0


class DescribeBuildDisplayNotes:
    def it_should_include_category_with_subcategory(self):
        service = TransactionQueryService()
        txn = _make_transaction(category="Groceries", subcategory="Produce")
        notes = service.build_display_notes(txn)
        assert "Groceries:Produce" in notes

    def it_should_include_category_without_subcategory(self):
        service = TransactionQueryService()
        txn = _make_transaction(category="Groceries", subcategory=None)
        notes = service.build_display_notes(txn)
        assert "Groceries" in notes
        assert ":" not in notes

    def it_should_include_transfer_info(self):
        service = TransactionQueryService()
        txn = _make_transaction(
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
        txn = _make_transaction(
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
        txn = _make_transaction(notes="Paid by cheque")
        notes = service.build_display_notes(txn)
        assert "Paid by cheque" in notes

    def it_should_combine_multiple_note_parts_with_pipe_separator(self):
        service = TransactionQueryService()
        txn = _make_transaction(category="Utilities", notes="Monthly bill")
        notes = service.build_display_notes(txn)
        assert " | " in notes
        assert "Utilities" in notes
        assert "Monthly bill" in notes

    def it_should_return_empty_string_when_no_notes(self):
        service = TransactionQueryService()
        txn = _make_transaction(category=None, notes=None)
        notes = service.build_display_notes(txn)
        assert notes == ""
