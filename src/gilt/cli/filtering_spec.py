from __future__ import annotations

from gilt.cli.filtering import find_by_account, find_uncategorized


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
