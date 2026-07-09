"""Specs for show_view.py — Rich rendering for the show command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.show_view as view_mod
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


class DescribeFmtValue:
    def it_should_return_placeholder_for_none(self):
        from gilt.cli.command.show_view import fmt_value

        assert fmt_value(None) == "—"

    def it_should_return_placeholder_for_empty_string(self):
        from gilt.cli.command.show_view import fmt_value

        assert fmt_value("") == "—"

    def it_should_return_string_representation_of_value(self):
        from gilt.cli.command.show_view import fmt_value

        assert fmt_value("hello") == "hello"
        assert fmt_value(42) == "42"


class DescribeFmtBool:
    def it_should_return_yes_for_truthy(self):
        from gilt.cli.command.show_view import fmt_bool

        assert fmt_bool(1) == "Yes"

    def it_should_return_no_for_falsy(self):
        from gilt.cli.command.show_view import fmt_bool

        assert fmt_bool(0) == "No"

    def it_should_return_placeholder_for_none(self):
        from gilt.cli.command.show_view import fmt_bool

        assert fmt_bool(None) == "—"


class DescribeFmtDescriptionHistory:
    def it_should_return_placeholder_for_none(self):
        from gilt.cli.command.show_view import fmt_description_history

        assert fmt_description_history(None) == "—"

    def it_should_format_json_array_as_bulleted_lines(self):
        from gilt.cli.command.show_view import fmt_description_history

        result = fmt_description_history('["desc1", "desc2"]')
        assert "desc1" in result
        assert "desc2" in result
        assert "•" in result


class DescribeBuildDetailTable:
    def it_should_return_a_table_with_transaction_id_row(self):
        from gilt.cli.command.show_view import build_detail_table

        row = {
            "transaction_id": "abcd1234efgh5678",
            "transaction_date": "2025-01-15",
            "account_id": "MYBANK_CHQ",
            "amount": "-50.00",
            "canonical_description": "EXAMPLE UTILITY",
        }
        table = build_detail_table(row)
        assert table is not None
        assert table.row_count > 0


class DescribeShowStatusMessages:
    def it_should_print_ambiguous_prefix(self):
        from gilt.cli.command.show_view import print_ambiguous_prefix

        output = _capture(lambda: print_ambiguous_prefix("aabbccdd"))
        assert "Ambiguous" in output
        assert "aabbccdd" in output

    def it_should_display_transaction_detail_header(self):
        from gilt.cli.command.show_view import display_transaction_detail

        output = _capture(lambda: display_transaction_detail({"transaction_id": "aabbccdd11223344"}))
        assert "Transaction Detail" in output
        assert "aabbccdd" in output
