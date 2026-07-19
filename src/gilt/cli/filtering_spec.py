from __future__ import annotations

from gilt.cli.filtering import (
    find_by_account,
    find_uncategorized,
    match_from_row,
    match_from_transaction,
)
from gilt.testing import make_transaction


class DescribeMatchFromRow:
    def it_should_return_account_id_and_group_from_row(self):
        row = {
            "transaction_id": "aabbccdd11223344",
            "transaction_date": "2025-03-10",
            "canonical_description": "SAMPLE STORE ANYTOWN",
            "amount": "-42.50",
            "currency": "CAD",
            "account_id": "MYBANK_CHQ",
        }

        account_id, group = match_from_row(row)

        assert account_id == "MYBANK_CHQ"
        assert group.group_id == "aabbccdd11223344"
        assert group.primary.account_id == "MYBANK_CHQ"


class DescribeMatchFromTransaction:
    def it_should_return_account_id_and_group_from_transaction(self):
        txn = make_transaction(account_id="MYBANK_CHQ", transaction_id="aabbccdd11223344")

        account_id, group = match_from_transaction(txn)

        assert account_id == "MYBANK_CHQ"
        assert group.group_id == "aabbccdd11223344"
        assert group.primary is txn


class DescribeFilterUncategorized:
    def it_should_filter_uncategorized_rows(self):
        rows = [
            {"account_id": "ACC1", "category": "Food"},
            {"account_id": "ACC2", "category": None},
            {"account_id": "ACC3"},
        ]

        result = find_uncategorized(rows)

        assert result == [{"account_id": "ACC2", "category": None}, {"account_id": "ACC3"}]

    def it_should_return_empty_when_all_categorized(self):
        rows = [
            {"account_id": "ACC1", "category": "Food"},
            {"account_id": "ACC2", "category": "Transport"},
        ]

        result = find_uncategorized(rows)

        assert result == []


class DescribeFilterByAccount:
    def it_should_filter_by_account(self):
        rows = [
            {"account_id": "ACC1", "amount": -100},
            {"account_id": "ACC2", "amount": -200},
            {"account_id": "ACC1", "amount": -50},
        ]

        result = find_by_account(rows, "ACC1")

        assert result == [
            {"account_id": "ACC1", "amount": -100},
            {"account_id": "ACC1", "amount": -50},
        ]

    def it_should_return_all_when_account_is_none(self):
        rows = [
            {"account_id": "ACC1", "amount": -100},
            {"account_id": "ACC2", "amount": -200},
        ]

        result = find_by_account(rows, None)

        assert result == rows
