"""Specs for mark_duplicate_review.py — interactive review for the mark-duplicate command."""

from __future__ import annotations

from unittest.mock import patch


def _make_primary_txn():
    return {
        "transaction_id": "abcd1234efgh5678",
        "transaction_date": "2025-01-15",
        "account_id": "MYBANK_CHQ",
        "amount": "-50.00",
        "canonical_description": "EXAMPLE UTILITY PAYMENT",
    }


def _make_duplicate_txn():
    return {
        "transaction_id": "wxyz9876mnop5432",
        "transaction_date": "2025-01-15",
        "account_id": "MYBANK_CHQ",
        "amount": "-50.00",
        "canonical_description": "EXAMPLE UTILITY PMT",
    }


class DescribePromptDescriptionChoice:
    def it_should_return_primary_description_when_user_chooses_1(self):
        from gilt.cli.command.mark_duplicate_review import prompt_description_choice

        primary = _make_primary_txn()
        duplicate = _make_duplicate_txn()
        with patch("gilt.cli.command.mark_duplicate_review.Prompt.ask", return_value="1"):
            result = prompt_description_choice(primary, duplicate)
        assert result == "EXAMPLE UTILITY PAYMENT"

    def it_should_return_duplicate_description_when_user_chooses_2(self):
        from gilt.cli.command.mark_duplicate_review import prompt_description_choice

        primary = _make_primary_txn()
        duplicate = _make_duplicate_txn()
        with patch("gilt.cli.command.mark_duplicate_review.Prompt.ask", return_value="2"):
            result = prompt_description_choice(primary, duplicate)
        assert result == "EXAMPLE UTILITY PMT"
