"""Specs for recategorize_view — Rich rendering functions."""

from __future__ import annotations

from datetime import date
from io import StringIO

from rich.console import Console

from gilt.cli.command.recategorize_view import (
    display_recategorize_matches,
    print_no_filter_matches,
    print_no_transactions_for_category,
    print_recategorized_success,
    print_renamed_success,
)
from gilt.model.account import Transaction, TransactionGroup


def _make_transaction(
    txn_id: str = "abcd1234abcd1234",
    description: str = "EXAMPLE UTILITY",
    amount: float = -42.50,
    account_id: str = "MYBANK_CHQ",
    category: str = "Food",
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
    import gilt.cli.command.recategorize_view as view_mod
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


class DescribeDisplayRecategorizeMatches:
    def it_should_display_transactions_to_recategorize_table(self):
        txn = _make_transaction()
        matches = [("MYBANK_CHQ", _make_group(txn))]
        output = _capture(lambda: display_recategorize_matches(matches, "Food", "Groceries"))
        assert "Transactions to Recategorize" in output
        assert "EXAMPLE UTILITY" in output

    def it_should_use_none_from_label_in_selection_mode(self):
        txn = _make_transaction()
        matches = [("MYBANK_CHQ", _make_group(txn))]
        output = _capture(lambda: display_recategorize_matches(matches, None, "Groceries"))
        assert "Transactions to Recategorize" in output


class DescribePrintNoTransactionsForCategory:
    def it_should_include_category_name(self):
        output = _capture(lambda: print_no_transactions_for_category("Food"))
        assert "Food" in output
        assert "No transactions found" in output


class DescribePrintNoFilterMatches:
    def it_should_print_yellow_notice(self):
        output = _capture(print_no_filter_matches)
        assert "No transactions match the given filters" in output


class DescribePrintRenamedSuccess:
    def it_should_include_count(self):
        output = _capture(lambda: print_renamed_success(7))
        assert "7" in output
        assert "Renamed" in output


class DescribePrintRecategorizedSuccess:
    def it_should_include_count(self):
        output = _capture(lambda: print_recategorized_success(4))
        assert "4" in output
        assert "Recategorized" in output
