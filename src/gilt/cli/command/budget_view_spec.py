"""Specs for budget_view.py — Rich rendering for the budget command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.budget_view as view_mod
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


def _make_summary(items=None, total_budgeted=500.0, total_actual=300.0, over_budget_count=0):
    from gilt.services.budget_service import BudgetItem, BudgetSummary

    if items is None:
        items = [
            BudgetItem(
                category_name="Utilities",
                subcategory_name=None,
                description=None,
                budget_amount=200.0,
                actual_amount=150.0,
                remaining=50.0,
                percent_used=75.0,
                is_over_budget=False,
                is_category_header=True,
            )
        ]
    remaining = total_budgeted - total_actual
    percent_used = (total_actual / total_budgeted * 100) if total_budgeted > 0 else 0
    return BudgetSummary(
        total_budgeted=total_budgeted,
        total_actual=total_actual,
        total_remaining=remaining,
        percent_used=percent_used,
        over_budget_count=over_budget_count,
        items=items,
    )


class DescribeDisplayBudgetReport:
    def it_should_display_budget_report_title(self):
        from gilt.cli.command.budget_view import display_budget_report

        summary = _make_summary()
        output = _capture(lambda: display_budget_report(summary, year=None, month=None, category_filter=None))
        assert "Budget Report" in output

    def it_should_include_category_filter_in_title(self):
        from gilt.cli.command.budget_view import display_budget_report

        summary = _make_summary()
        output = _capture(
            lambda: display_budget_report(summary, year=None, month=None, category_filter="Housing")
        )
        assert "Housing" in output

    def it_should_not_include_category_filter_in_title_when_absent(self):
        from gilt.cli.command.budget_view import display_budget_report

        summary = _make_summary()
        output = _capture(
            lambda: display_budget_report(summary, year=None, month=None, category_filter=None)
        )
        assert "Housing" not in output

    def it_should_include_year_in_title_when_provided(self):
        from gilt.cli.command.budget_view import display_budget_report

        summary = _make_summary()
        output = _capture(
            lambda: display_budget_report(summary, year=2025, month=None, category_filter=None)
        )
        assert "2025" in output

    def it_should_not_include_year_in_title_when_absent(self):
        from gilt.cli.command.budget_view import display_budget_report

        summary = _make_summary()
        output = _capture(
            lambda: display_budget_report(summary, year=None, month=None, category_filter=None)
        )
        assert "2025" not in output

    def it_should_show_total_budgeted_amount(self):
        from gilt.cli.command.budget_view import display_budget_report

        summary = _make_summary(total_budgeted=1234.0, total_actual=300.0)
        output = _capture(
            lambda: display_budget_report(summary, year=None, month=None, category_filter=None)
        )
        assert "1,234" in output
