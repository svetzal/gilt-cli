"""Specs for reingest_view.py — Rich rendering for the reingest command."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.reingest_view as view_mod
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


class DescribePrintNoSourceFiles:
    def it_should_mention_the_account(self):
        from gilt.cli.command.reingest_view import print_no_source_files

        assert "MYBANK_CHQ" in _capture(lambda: print_no_source_files("MYBANK_CHQ"))


class DescribeDisplayReingestPlan:
    def it_should_list_source_files_and_purge_counts(self):
        from gilt.cli.command.reingest_view import display_reingest_plan

        account_files = [(Path("mybank_chq_2025.csv"), "MYBANK_CHQ")]
        purge_plan = SimpleNamespace(event_ids=[1, 2, 3], transaction_ids=[1, 2])
        output = _capture(
            lambda: display_reingest_plan(
                "MYBANK_CHQ", account_files, Path("MYBANK_CHQ.csv"), purge_plan
            )
        )
        assert "MYBANK_CHQ" in output
        assert "mybank_chq_2025.csv" in output
        assert "3" in output
        assert "2" in output


class DescribeReingestProgressMessages:
    def it_should_print_removed_ledger(self):
        from gilt.cli.command.reingest_view import print_removed_ledger

        assert "MYBANK_CHQ.csv" in _capture(lambda: print_removed_ledger("MYBANK_CHQ.csv"))

    def it_should_print_purge_results(self):
        from gilt.cli.command.reingest_view import print_purge_results

        result = SimpleNamespace(
            events_purged=5, projections_purged=4, cache_entries_purged=1
        )
        output = _capture(lambda: print_purge_results(result))
        assert "5" in output
        assert "4" in output
        assert "1" in output

    def it_should_print_wrote_path(self):
        from gilt.cli.command.reingest_view import print_wrote

        assert "out.csv" in _capture(lambda: print_wrote(Path("out.csv")))

    def it_should_print_rebuilding_header(self):
        from gilt.cli.command.reingest_view import print_rebuilding

        assert "Rebuilding" in _capture(print_rebuilding)

    def it_should_print_transfer_metadata(self):
        from gilt.cli.command.reingest_view import print_transfer_metadata

        assert "2" in _capture(lambda: print_transfer_metadata(2))

    def it_should_print_rebuilt(self):
        from gilt.cli.command.reingest_view import print_rebuilt

        assert "42" in _capture(lambda: print_rebuilt(42))

    def it_should_print_done_summary(self):
        from gilt.cli.command.reingest_view import print_done

        output = _capture(lambda: print_done(3, "MYBANK_CHQ"))
        assert "3" in output
        assert "MYBANK_CHQ" in output
