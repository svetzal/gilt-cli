"""Specs for backfill_events_view.py — Rich rendering for the backfill-events command."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.backfill_events_view as view_mod
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


class DescribeDisplaySummary:
    def it_should_show_migration_counts(self):
        from gilt.cli.command.backfill_events_view import display_summary
        from gilt.services.event_migration_service import MigrationStats

        stats = MigrationStats(
            transaction_imported=5,
            transaction_categorized=3,
            budget_created=2,
            errors=0,
        )
        output = _capture(
            lambda: display_summary(stats, dry_run=True, effective_event_store_path=Path("/tmp/events.db"))
        )
        assert "5" in output
        assert "3" in output
        assert "2" in output

    def it_should_show_dry_run_message_when_dry_run_is_true(self):
        from gilt.cli.command.backfill_events_view import display_summary
        from gilt.services.event_migration_service import MigrationStats

        stats = MigrationStats(
            transaction_imported=1,
            transaction_categorized=0,
            budget_created=0,
            errors=0,
        )
        output = _capture(
            lambda: display_summary(stats, dry_run=True, effective_event_store_path=Path("/tmp/events.db"))
        )
        assert "dry run" in output.lower()

    def it_should_show_success_message_when_not_dry_run(self):
        from gilt.cli.command.backfill_events_view import display_summary
        from gilt.services.event_migration_service import MigrationStats

        stats = MigrationStats(
            transaction_imported=1,
            transaction_categorized=0,
            budget_created=0,
            errors=0,
        )
        output = _capture(
            lambda: display_summary(
                stats, dry_run=False, effective_event_store_path=Path("/tmp/events.db")
            )
        )
        assert "successfully" in output.lower() or "written" in output.lower()
