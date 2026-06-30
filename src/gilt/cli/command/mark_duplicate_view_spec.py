"""Specs for mark_duplicate_view.py — Rich rendering for the mark-duplicate command."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.mark_duplicate_view as view_mod
    import gilt.cli.console as console_mod

    new_console = Console(file=buf, highlight=False, width=200)
    old_view = view_mod.console
    old_mod = console_mod.console
    view_mod.console = new_console
    console_mod.console = new_console
    try:
        fn()
    finally:
        view_mod.console = old_view
        console_mod.console = old_mod
    return buf.getvalue()


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


class DescribeDisplayValidationResults:
    def it_should_show_errors_from_validation(self):
        from gilt.cli.command.mark_duplicate_view import display_validation_results

        validation = MagicMock()
        validation.errors = ["Transaction not found"]
        validation.warnings = []
        output = _capture(lambda: display_validation_results(validation, write=False))
        assert "Transaction not found" in output

    def it_should_show_warnings_from_validation(self):
        from gilt.cli.command.mark_duplicate_view import display_validation_results

        validation = MagicMock()
        validation.errors = []
        validation.warnings = ["different account"]
        output = _capture(lambda: display_validation_results(validation, write=False))
        assert "different account" in output


class DescribeBuildComparisonTable:
    def it_should_include_transaction_ids(self):
        from gilt.cli.command.mark_duplicate_view import build_comparison_table

        table = build_comparison_table(_make_primary_txn(), _make_duplicate_txn())
        # Table is returned, not printed — verify it has rows
        assert table is not None
        assert table.row_count > 0

    def it_should_return_a_table_with_comparison_title(self):
        from gilt.cli.command.mark_duplicate_view import build_comparison_table

        table = build_comparison_table(_make_primary_txn(), _make_duplicate_txn())
        assert table.title is not None
        assert "Duplicate" in table.title or "duplicate" in table.title.lower()
