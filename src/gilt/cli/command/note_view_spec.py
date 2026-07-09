"""Specs for note_view.py — Rich rendering for the note command."""

from __future__ import annotations

from datetime import date as dt_date
from io import StringIO
from pathlib import Path

from rich.console import Console

from gilt.model.account import Transaction, TransactionGroup


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.note_view as view_mod
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


def _group(
    tid: str = "abcd1234abcd1234",
    description: str = "SAMPLE STORE",
    amount: float = -12.5,
    notes: str | None = None,
) -> TransactionGroup:
    txn = Transaction(
        transaction_id=tid,
        date=dt_date(2025, 4, 4),
        description=description,
        amount=amount,
        currency="CAD",
        account_id="MYBANK_CHQ",
        notes=notes,
    )
    return TransactionGroup(group_id=tid, primary=txn)


class DescribeHighlightPrefix:
    def it_should_wrap_matching_prefix_in_markup(self):
        from gilt.cli.command.note_view import highlight_prefix

        assert highlight_prefix("ANTHROPIC AI", "anthropic") == "[bold yellow]ANTHROPIC[/] AI"

    def it_should_return_description_unchanged_when_prefix_absent(self):
        from gilt.cli.command.note_view import highlight_prefix

        assert highlight_prefix("SAMPLE STORE", "acme") == "SAMPLE STORE"

    def it_should_return_description_unchanged_when_prefix_empty(self):
        from gilt.cli.command.note_view import highlight_prefix

        assert highlight_prefix("SAMPLE STORE", "") == "SAMPLE STORE"


class DescribeDisplayMatches:
    def it_should_render_transaction_and_new_note(self):
        from gilt.cli.command.note_view import display_matches

        groups = [_group(description="SAMPLE STORE", notes="old")]
        output = _capture(lambda: display_matches("MYBANK_CHQ", groups, "new-note"))
        assert "SAMPLE STORE" in output
        assert "new-note" in output
        assert "MYBANK_CHQ" in output

    def it_should_highlight_the_prefix_when_supplied(self):
        from gilt.cli.command.note_view import display_matches

        groups = [_group(description="ANTHROPIC AI INC")]
        output = _capture(
            lambda: display_matches("MYBANK_CHQ", groups, "ai", desc_prefix="anthropic")
        )
        assert "ANTHROPIC" in output


class DescribePrintNoteTargetSummary:
    def it_should_report_single_transaction_by_txid(self):
        from gilt.cli.command.note_view import print_note_target_summary

        groups = [_group(tid="deadbeefdeadbeef")]
        output = _capture(
            lambda: print_note_target_summary(
                groups, "MYBANK_CHQ", "deadbeef", None, None, None, None
            )
        )
        assert "deadbeef" in output
        assert "Will set note for transaction" in output

    def it_should_report_batch_criteria(self):
        from gilt.cli.command.note_view import print_note_target_summary

        groups = [_group(), _group(tid="efef5678efef5678")]
        output = _capture(
            lambda: print_note_target_summary(
                groups, "MYBANK_CHQ", None, "SAMPLE STORE", None, None, -12.5
            )
        )
        assert "2 transactions" in output
        assert "MYBANK_CHQ" in output
        assert "description='SAMPLE STORE'" in output
        assert "amount=-12.5" in output


class DescribePrintNoTransactionsInLedger:
    def it_should_include_the_ledger_path(self):
        from gilt.cli.command.note_view import print_no_transactions_in_ledger

        output = _capture(
            lambda: print_no_transactions_in_ledger(Path("data/accounts/MYBANK_CHQ.csv"))
        )
        assert "No transactions found in ledger" in output
        assert "MYBANK_CHQ.csv" in output


class DescribePrintNoMatches:
    def it_should_state_no_transactions_matched(self):
        from gilt.cli.command.note_view import print_no_matches

        output = _capture(print_no_matches)
        assert "No transactions matched the specified criteria." in output


class DescribePrintNotesSaved:
    def it_should_report_the_applied_count(self):
        from gilt.cli.command.note_view import print_notes_saved

        output = _capture(lambda: print_notes_saved(3))
        assert "Saved notes to ledger successfully." in output
        assert "3 transaction(s)" in output
