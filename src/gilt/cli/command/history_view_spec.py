"""Specs for history_view.py — Rich rendering for the history command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.history_view as view_mod
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


def _make_history_row(category="Utilities", subcategory="Internet", count=5, total=-250.0):
    from gilt.storage.projection_queries import CategoryHistoryRow

    return CategoryHistoryRow(
        category=category,
        subcategory=subcategory,
        count=count,
        total=total,
        min_amount=-100.0,
        max_amount=-50.0,
        latest_date="2025-06-01",
    )


class DescribeDisplayHistoryTable:
    def it_should_render_the_pattern_in_the_title(self):
        from gilt.cli.command.history_view import display_history_table

        rows = [_make_history_row()]
        output = _capture(
            lambda: display_history_table(rows, "EXAMPLE UTILITY", None, None, None)
        )
        assert "EXAMPLE UTILITY" in output

    def it_should_show_category_data(self):
        from gilt.cli.command.history_view import display_history_table

        rows = [_make_history_row(category="Utilities")]
        output = _capture(
            lambda: display_history_table(rows, "EXAMPLE", None, None, None)
        )
        assert "Utilities" in output

    def it_should_include_account_filter_in_title(self):
        from gilt.cli.command.history_view import display_history_table

        rows = [_make_history_row()]
        output = _capture(
            lambda: display_history_table(rows, "EXAMPLE", "MYBANK_CHQ", None, None)
        )
        assert "MYBANK_CHQ" in output

    def it_should_not_include_account_filter_in_title_when_absent(self):
        from gilt.cli.command.history_view import display_history_table

        rows = [_make_history_row()]
        output = _capture(
            lambda: display_history_table(rows, "EXAMPLE", None, None, None)
        )
        assert "MYBANK_CHQ" not in output


class DescribeHistoryStatusMessages:
    def it_should_print_invalid_date_with_field_and_value(self):
        from gilt.cli.command.history_view import print_invalid_date

        output = _capture(lambda: print_invalid_date("date-from", "not-a-date"))
        assert "date-from" in output
        assert "not-a-date" in output

    def it_should_print_no_matches_with_pattern(self):
        from gilt.cli.command.history_view import print_no_matches

        assert "SAMPLE" in _capture(lambda: print_no_matches("SAMPLE"))
