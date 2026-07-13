"""Specs for migrate_to_events_view.py — Rich rendering for the migrate-to-events command.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.migrate_to_events_view as view_mod
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


class DescribePrintMigrationHeader:
    def it_should_mention_event_sourcing(self):
        from gilt.cli.command.migrate_to_events_view import print_migration_header

        assert "Event Sourcing" in _capture(print_migration_header)


class DescribePrintStepPreconditions:
    def it_should_mention_step_1(self):
        from gilt.cli.command.migrate_to_events_view import print_step_preconditions

        assert "Step 1" in _capture(print_step_preconditions)


class DescribePrintEventStoreExistsWarning:
    def it_should_show_count_path_and_options(self):
        from gilt.cli.command.migrate_to_events_view import print_event_store_exists_warning

        output = _capture(lambda: print_event_store_exists_warning(7, Path("data/events.db")))
        assert "7" in output
        assert "data/events.db" in output
        assert "--force" in output


class DescribeDisplayPreconditionsSuccess:
    def it_should_report_ledger_count_and_categories_present(self):
        from gilt.cli.command.migrate_to_events_view import display_preconditions_success

        output = _capture(
            lambda: display_preconditions_success(
                [Path("MYBANK_CHQ.csv")], True, Path("config/categories.yml")
            )
        )
        assert "1" in output
        assert "Categories config exists" in output

    def it_should_warn_when_categories_missing(self):
        from gilt.cli.command.migrate_to_events_view import display_preconditions_success

        output = _capture(
            lambda: display_preconditions_success(
                [Path("MYBANK_CHQ.csv")], False, Path("config/categories.yml")
            )
        )
        assert "config/categories.yml" in output
        assert "skip budget migration" in output


class DescribeDisplayMigrationPlan:
    def it_should_list_backfill_and_projection_steps(self):
        from gilt.cli.command.migrate_to_events_view import display_migration_plan

        output = _capture(lambda: display_migration_plan([Path("MYBANK_CHQ.csv")], True))
        assert "Migration would" in output
        assert "Backfill events from 1" in output
        assert "budget events" in output

    def it_should_omit_budget_line_when_no_categories(self):
        from gilt.cli.command.migrate_to_events_view import display_migration_plan

        output = _capture(lambda: display_migration_plan([Path("MYBANK_CHQ.csv")], False))
        assert "budget events" not in output

    def it_should_not_contain_dropped_dry_run_wording(self):
        from gilt.cli.command.migrate_to_events_view import display_migration_plan

        output = _capture(lambda: display_migration_plan([Path("MYBANK_CHQ.csv")], True))
        assert "DRY RUN MODE" not in output
        assert "Use --write" not in output


class DescribeStepHeaders:
    def it_should_print_step_backfill(self):
        from gilt.cli.command.migrate_to_events_view import print_step_backfill

        assert "Step 2" in _capture(print_step_backfill)

    def it_should_print_step_projections(self):
        from gilt.cli.command.migrate_to_events_view import print_step_projections

        assert "Step 3" in _capture(print_step_projections)

    def it_should_print_step_validating(self):
        from gilt.cli.command.migrate_to_events_view import print_step_validating

        assert "Step 4" in _capture(print_step_validating)


class DescribeEventAndProjectionCounts:
    def it_should_print_transaction_events_created(self):
        from gilt.cli.command.migrate_to_events_view import print_transaction_events_created

        assert "5" in _capture(lambda: print_transaction_events_created(5))

    def it_should_print_budget_events_created(self):
        from gilt.cli.command.migrate_to_events_view import print_budget_events_created

        assert "3" in _capture(lambda: print_budget_events_created(3))

    def it_should_print_transaction_projections_built(self):
        from gilt.cli.command.migrate_to_events_view import print_transaction_projections_built

        assert "12" in _capture(lambda: print_transaction_projections_built(12))

    def it_should_print_budget_projections_built(self):
        from gilt.cli.command.migrate_to_events_view import print_budget_projections_built

        assert "4" in _capture(lambda: print_budget_projections_built(4))


class DescribeDisplayValidationResult:
    def it_should_return_0_and_report_passes_when_valid(self):
        from gilt.cli.command.migrate_to_events_view import display_validation_result

        result = SimpleNamespace(
            transaction_count_match=True,
            budget_count_match=True,
            sample_transactions_match=True,
            errors=[],
        )
        captured: list[int] = []
        output = _capture(lambda: captured.append(display_validation_result(result, True)))
        assert captured == [0]
        assert "Transaction count matches" in output
        assert "Budget count matches" in output
        assert "Sample transaction validation passed" in output

    def it_should_return_1_and_print_errors_when_invalid(self):
        from gilt.cli.command.migrate_to_events_view import display_validation_result

        result = SimpleNamespace(
            transaction_count_match=False,
            budget_count_match=False,
            sample_transactions_match=False,
            errors=["count mismatch"],
        )
        captured: list[int] = []
        output = _capture(lambda: captured.append(display_validation_result(result, True)))
        assert captured == [1]
        assert "count mismatch" in output


class DescribeDisplayCompletionSummary:
    def it_should_show_paths_and_total_events(self):
        from gilt.cli.command.migrate_to_events_view import display_completion_summary

        output = _capture(
            lambda: display_completion_summary(
                Path("data/events.db"), Path("data/projections.db"), 10, 2, 0
            )
        )
        assert "data/events.db" in output
        assert "data/projections.db" in output
        assert "12" in output
        assert "Migration Complete" in output

    def it_should_warn_when_errors_occurred(self):
        from gilt.cli.command.migrate_to_events_view import display_completion_summary

        output = _capture(
            lambda: display_completion_summary(
                Path("data/events.db"), Path("data/projections.db"), 10, 2, 3
            )
        )
        assert "3 error(s)" in output
