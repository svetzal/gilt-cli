"""Specs for rebuild_projections_view.py — Rich rendering for the rebuild-projections command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.rebuild_projections_view as view_mod
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


def _make_txn(account_id="MYBANK_CHQ"):
    return {
        "account_id": account_id,
        "transaction_id": "abcd1234efgh5678",
        "description_history": None,
        "vendor": None,
    }


class DescribeDisplayRebuildSummary:
    def it_should_display_total_transaction_count(self):
        from gilt.cli.command.rebuild_projections_view import display_rebuild_summary

        txns = [_make_txn(), _make_txn()]
        output = _capture(lambda: display_rebuild_summary(txns, txns))
        assert "2" in output

    def it_should_display_account_breakdown(self):
        from gilt.cli.command.rebuild_projections_view import display_rebuild_summary

        txns = [_make_txn("MYBANK_CHQ"), _make_txn("MYBANK_CC")]
        output = _capture(lambda: display_rebuild_summary(txns, txns))
        assert "MYBANK_CHQ" in output
        assert "MYBANK_CC" in output

    def it_should_display_summary_label(self):
        from gilt.cli.command.rebuild_projections_view import display_rebuild_summary

        txns = [_make_txn()]
        output = _capture(lambda: display_rebuild_summary(txns, txns))
        assert "Summary" in output
