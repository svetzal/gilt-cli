"""Specs for categorize_view — Rich rendering functions."""

from __future__ import annotations

from datetime import date
from io import StringIO

from rich.console import Console

from gilt.cli.command.categorize import ResolvedEntry
from gilt.cli.command.categorize_view import (
    display_batch_preview,
    display_categorization_matches,
    print_batch_mode_notice,
    print_categorized_success,
    print_category_add_hint,
    print_category_warning,
    print_no_entries,
    print_no_matches,
    report_categorization_result,
)
from gilt.model.account import Transaction, TransactionGroup


def _make_transaction(
    txn_id: str = "abcd1234abcd1234",
    description: str = "EXAMPLE UTILITY",
    amount: float = -42.50,
    account_id: str = "MYBANK_CHQ",
    category: str | None = None,
) -> Transaction:
    return Transaction(
        transaction_id=txn_id,
        date=date(2025, 1, 15),
        description=description,
        amount=amount,
        currency="CAD",
        account_id=account_id,
        category=category,
    )


def _make_group(txn: Transaction) -> TransactionGroup:
    return TransactionGroup(group_id=txn.transaction_id, primary=txn)


def _capture(fn) -> str:
    """Run fn() and capture console output to a string."""
    buf = StringIO()
    import gilt.cli.command.categorize_view as view_mod
    import gilt.cli.console as console_mod

    new_console = Console(file=buf, highlight=False, width=200)
    old_view_console = view_mod.console
    old_mod_console = console_mod.console
    view_mod.console = new_console
    console_mod.console = new_console
    try:
        fn()
    finally:
        view_mod.console = old_view_console
        console_mod.console = old_mod_console
    return buf.getvalue()


class DescribeDisplayCategorizationMatches:
    def it_should_display_matched_transactions_table(self):
        txn = _make_transaction()
        matches = [("MYBANK_CHQ", _make_group(txn))]
        output = _capture(lambda: display_categorization_matches(matches, "Utilities", None))
        assert "Matched Transactions" in output
        assert "EXAMPLE UTILITY" in output

    def it_should_show_new_category_in_table(self):
        txn = _make_transaction(category="Food")
        matches = [("MYBANK_CHQ", _make_group(txn))]
        output = _capture(
            lambda: display_categorization_matches(matches, "Utilities", "Electric")
        )
        assert "Utilities" in output


class DescribeDisplayBatchPreview:
    def it_should_display_batch_categorization_preview(self):
        txn = _make_transaction(txn_id="abcd1234abcd1234")
        group = _make_group(txn)
        preview_matches = [("MYBANK_CHQ", group)]
        resolved = [
            ResolvedEntry(
                transaction_id="abcd1234abcd1234",
                account_id="MYBANK_CHQ",
                category="Utilities",
                subcategory=None,
            )
        ]
        output = _capture(lambda: display_batch_preview(preview_matches, resolved))
        assert "Batch Categorization Preview" in output
        assert "EXAMPLE UTILITY" in output


class DescribeReportCategorizationResult:
    def it_should_print_success_when_write_and_result_zero(self):
        txn = _make_transaction()
        matches = [("MYBANK_CHQ", _make_group(txn))]
        output = _capture(lambda: report_categorization_result(matches, 0, 0, True))
        assert "Categorized 1 transaction" in output

    def it_should_print_recategorized_warning_when_any_had_category(self):
        txn = _make_transaction(category="Food")
        matches = [("MYBANK_CHQ", _make_group(txn))]
        output = _capture(lambda: report_categorization_result(matches, 0, 1, True))
        assert "re-categorized" in output

    def it_should_print_nothing_when_dry_run(self):
        txn = _make_transaction()
        matches = [("MYBANK_CHQ", _make_group(txn))]
        output = _capture(lambda: report_categorization_result(matches, 0, 0, False))
        assert output.strip() == ""


class DescribePrintNoEntries:
    def it_should_print_yellow_notice(self):
        output = _capture(print_no_entries)
        assert "No entries found in batch input" in output


class DescribePrintNoMatches:
    def it_should_print_yellow_notice(self):
        output = _capture(print_no_matches)
        assert "No matching transactions found" in output


class DescribePrintBatchModeNotice:
    def it_should_include_count(self):
        output = _capture(lambda: print_batch_mode_notice(5))
        assert "5" in output
        assert "Batch mode" in output


class DescribePrintCategorizedSuccess:
    def it_should_include_count(self):
        output = _capture(lambda: print_categorized_success(3))
        assert "3" in output
        assert "Categorized" in output


class DescribePrintCategoryWarning:
    def it_should_include_message(self):
        output = _capture(lambda: print_category_warning("subcategory ignored"))
        assert "subcategory ignored" in output


class DescribePrintCategoryAddHint:
    def it_should_include_category_name(self):
        output = _capture(lambda: print_category_add_hint("Utilities"))
        assert "Utilities" in output
        assert "gilt category" in output
