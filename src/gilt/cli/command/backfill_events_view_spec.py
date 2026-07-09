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


class _StubValidation:
    def __init__(
        self,
        transaction_count_match=True,
        budget_count_match=True,
        sample_transactions_match=True,
    ):
        self.transaction_count_match = transaction_count_match
        self.budget_count_match = budget_count_match
        self.sample_transactions_match = sample_transactions_match


class DescribePrintMigrationHeader:
    def it_should_show_the_manual_backfill_banner(self):
        from gilt.cli.command.backfill_events_view import print_migration_header

        output = _capture(print_migration_header)
        assert "Manual Backfill" in output


class DescribePrintTransactionStep:
    def it_should_show_the_step_one_header(self):
        from gilt.cli.command.backfill_events_view import print_transaction_step

        output = _capture(print_transaction_step)
        assert "Step 1" in output


class DescribePrintNoLedgers:
    def it_should_show_the_no_ledgers_notice(self):
        from gilt.cli.command.backfill_events_view import print_no_ledgers

        output = _capture(print_no_ledgers)
        assert "No ledger files found" in output


class DescribePrintBudgetStep:
    def it_should_show_the_step_two_header(self):
        from gilt.cli.command.backfill_events_view import print_budget_step

        output = _capture(print_budget_step)
        assert "Step 2" in output


class DescribeDisplayBudgets:
    def it_should_show_each_budget_line(self):
        from gilt.cli.command.backfill_events_view import display_budgets

        output = _capture(
            lambda: display_budgets(["  Groceries: $500.00/monthly"], budget_created=1)
        )
        assert "Groceries" in output

    def it_should_show_no_budgets_notice_when_none_created(self):
        from gilt.cli.command.backfill_events_view import display_budgets

        output = _capture(lambda: display_budgets([], budget_created=0))
        assert "No budgets found" in output


class DescribeDisplayProjectionRebuild:
    def it_should_show_the_processed_event_counts(self):
        from gilt.cli.command.backfill_events_view import display_projection_rebuild

        output = _capture(lambda: display_projection_rebuild(7, 4))
        assert "Step 3" in output
        assert "7" in output
        assert "4" in output


class DescribeDisplayValidationChecks:
    def it_should_show_passing_check_lines(self):
        from gilt.cli.command.backfill_events_view import display_validation_checks

        output = _capture(lambda: display_validation_checks(_StubValidation()))
        assert "Running validation checks" in output
        assert "Transaction count matches" in output
        assert "Budget count matches" in output


class DescribePrintValidationErrors:
    def it_should_list_the_validation_errors(self):
        from gilt.cli.command.backfill_events_view import print_validation_errors

        output = _capture(lambda: print_validation_errors(["mismatch in totals"]))
        assert "Validation Errors" in output
        assert "mismatch in totals" in output


class DescribePrintAllValidationsPassed:
    def it_should_show_the_all_clear_message(self):
        from gilt.cli.command.backfill_events_view import print_all_validations_passed

        output = _capture(print_all_validations_passed)
        assert "All validations passed" in output


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
