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


class DescribePrintEventStoreMissingHint:
    def it_should_mention_running_ingest(self):
        from gilt.cli.command.rebuild_projections_view import print_event_store_missing_hint

        output = _capture(print_event_store_missing_hint)
        assert "ingest" in output


class DescribeDisplayRebuildHeader:
    def it_should_display_mode_and_paths(self):
        from pathlib import Path

        from gilt.cli.command.rebuild_projections_view import display_rebuild_header

        output = _capture(
            lambda: display_rebuild_header("incremental", Path("events.db"), Path("projections.db"))
        )
        assert "incremental" in output
        assert "events.db" in output
        assert "projections.db" in output


class DescribePrintEmptyEventStoreWarning:
    def it_should_warn_that_store_is_empty(self):
        from gilt.cli.command.rebuild_projections_view import print_empty_event_store_warning

        output = _capture(print_empty_event_store_warning)
        assert "empty" in output


class DescribePrintProcessingEvents:
    def it_should_display_event_count(self):
        from gilt.cli.command.rebuild_projections_view import print_processing_events

        output = _capture(lambda: print_processing_events(42))
        assert "42" in output


class DescribePrintAlreadyUpToDate:
    def it_should_report_up_to_date(self):
        from gilt.cli.command.rebuild_projections_view import print_already_up_to_date

        output = _capture(print_already_up_to_date)
        assert "up to date" in output


class DescribePrintProcessedEvents:
    def it_should_display_processed_count(self):
        from gilt.cli.command.rebuild_projections_view import print_processed_events

        output = _capture(lambda: print_processed_events(7))
        assert "7" in output


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
