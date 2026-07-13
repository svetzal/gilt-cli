"""Specs for ingest_view.py — Rich rendering for the ingest command."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.ingest_view as view_mod
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


class DescribeDisplayPlan:
    def it_should_list_matched_inputs_and_accounts(self):
        from gilt.cli.command.ingest_view import display_plan

        plan = [(Path("mybank_export.csv"), "MYBANK_CHQ"), (Path("mystery.csv"), None)]
        output = _capture(lambda: display_plan(plan, 2))
        assert "mybank_export.csv" in output
        assert "MYBANK_CHQ" in output
        assert "UNKNOWN" in output


class DescribeLedgerCountDisplays:
    def it_should_display_pre_counts(self):
        from gilt.cli.command.ingest_view import display_pre_counts

        output = _capture(lambda: display_pre_counts({"MYBANK_CHQ.csv": 5}))
        assert "MYBANK_CHQ.csv" in output
        assert "5" in output

    def it_should_skip_empty_pre_counts(self):
        from gilt.cli.command.ingest_view import display_pre_counts

        assert _capture(lambda: display_pre_counts({})) == ""

    def it_should_display_post_counts_with_delta(self):
        from gilt.cli.command.ingest_view import display_post_counts

        output = _capture(lambda: display_post_counts({"MYBANK_CHQ.csv": 7}, {"MYBANK_CHQ.csv": 5}))
        assert "+2" in output


class DescribeIngestStatusMessages:
    def it_should_print_skip(self):
        from gilt.cli.command.ingest_view import print_skip

        assert "mystery.csv" in _capture(lambda: print_skip("mystery.csv"))

    def it_should_print_wrote(self):
        from gilt.cli.command.ingest_view import print_wrote

        assert "out.csv" in _capture(lambda: print_wrote(Path("out.csv")))

    def it_should_print_transfer_metadata(self):
        from gilt.cli.command.ingest_view import print_transfer_metadata

        assert "3" in _capture(lambda: print_transfer_metadata(3))

    def it_should_print_no_transfers(self):
        from gilt.cli.command.ingest_view import print_no_transfers

        assert "No transfer links" in _capture(print_no_transfers)

    def it_should_print_processed(self):
        from gilt.cli.command.ingest_view import print_processed

        assert "9" in _capture(lambda: print_processed(9))

    def it_should_print_projection_total(self):
        from gilt.cli.command.ingest_view import print_projection_total

        assert "42" in _capture(lambda: print_projection_total(42))

    def it_should_print_auto_categorized(self):
        from gilt.cli.command.ingest_view import print_auto_categorized

        assert "4" in _capture(lambda: print_auto_categorized(4))

    def it_should_print_event_store_total(self):
        from gilt.cli.command.ingest_view import print_event_store_total

        assert "100" in _capture(lambda: print_event_store_total(100))

    def it_should_print_done(self):
        from gilt.cli.command.ingest_view import print_done

        output = _capture(lambda: print_done(3, 1))
        assert "Written=3" in output
        assert "Skipped=1" in output
