from __future__ import annotations

from datetime import date

from rich.table import Table

from gilt.cli.console import (
    confirm_interactively,
    display_category_change_matches,
    display_transaction_matches,
    print_error,
    print_error_list,
    print_transaction_table,
    print_warning,
)
from gilt.model.account import Transaction, TransactionGroup


class DescribePrintError:
    def it_should_print_error_with_red_prefix(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")

        print_error("something went wrong")

        mock_console.print.assert_called_once_with("[red]Error:[/] something went wrong")

    def it_should_include_the_message_verbatim(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")

        print_error("file not found: /data/foo.csv")

        args = mock_console.print.call_args[0][0]
        assert "file not found: /data/foo.csv" in args


class DescribePrintWarning:
    def it_should_print_warning_with_yellow_prefix(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")

        print_warning("deprecated feature used")

        mock_console.print.assert_called_once_with("[yellow]Warning:[/] deprecated feature used")

    def it_should_include_the_message_verbatim(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")

        print_warning("only 3 items found")

        args = mock_console.print.call_args[0][0]
        assert "only 3 items found" in args


class DescribePrintErrorList:
    def it_should_print_heading_and_bullets(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")

        print_error_list("Validation errors", ["field required", "value out of range"])

        calls = [c[0][0] for c in mock_console.print.call_args_list]
        assert calls[0] == "[red]Validation errors:[/]"
        assert calls[1] == "  • field required"
        assert calls[2] == "  • value out of range"

    def it_should_print_nothing_for_empty_list(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")

        print_error_list("No errors", [])

        calls = [c[0][0] for c in mock_console.print.call_args_list]
        assert len(calls) == 1
        assert calls[0] == "[red]No errors:[/]"


class DescribePrintTransactionTable:
    def it_should_print_overflow_message_when_exceeding_limit(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")
        table = Table()
        for _ in range(55):
            table.add_row("a")

        print_transaction_table(table, total_count=55, display_limit=50)

        overflow_call = mock_console.print.call_args_list[-1]
        assert "5 more" in str(overflow_call)

    def it_should_not_print_overflow_message_when_at_limit(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")
        table = Table()
        for _ in range(50):
            table.add_row("a")

        print_transaction_table(table, total_count=50, display_limit=50)

        calls = [str(c) for c in mock_console.print.call_args_list]
        assert not any("more" in c for c in calls)

    def it_should_not_print_overflow_message_when_below_limit(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")
        table = Table()
        for _ in range(10):
            table.add_row("a")

        print_transaction_table(table, total_count=10, display_limit=50)

        calls = [str(c) for c in mock_console.print.call_args_list]
        assert not any("more" in c for c in calls)


class DescribeDisplayTransactionMatches:
    def it_should_create_and_print_a_table_with_all_matches(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")
        matches = [
            ("ACC1", "aaaa0001", "2025-01-01", "SAMPLE STORE", "-42.50", "Food"),
            ("ACC2", "bbbb0002", "2025-01-02", "ACME CORP", "-10.00", "Bills"),
        ]

        def row_fn(item):
            return item

        display_transaction_matches(
            "Test Table",
            [("Category", {"style": "green"})],
            matches,
            row_fn,
        )

        assert mock_console.print.called

    def it_should_limit_rendered_rows_to_display_limit(self, mocker):
        mocker.patch("gilt.cli.console.console")
        rendered_rows = []
        matches = list(range(60))

        def row_fn(item):
            rendered_rows.append(item)
            return (str(item), str(item), str(item), str(item), str(item))

        display_transaction_matches(
            "Test",
            [],
            matches,
            row_fn,
            display_limit=50,
        )

        assert len(rendered_rows) == 50

    def it_should_pass_total_count_to_print_transaction_table(self, mocker):
        mock_print_table = mocker.patch("gilt.cli.console.print_transaction_table")
        mocker.patch("gilt.cli.console.build_transaction_table")
        matches = list(range(55))

        display_transaction_matches(
            "Test",
            [],
            matches,
            lambda item: (str(item),),
            display_limit=50,
        )

        _, kwargs = mock_print_table.call_args
        assert kwargs.get("display_limit") == 50
        positional = mock_print_table.call_args[0]
        assert positional[1] == 55

    def it_should_render_empty_table_when_matches_is_empty(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")

        display_transaction_matches("Test", [], [], lambda item: (str(item),))

        assert mock_console.print.called


class DescribeConfirmInteractively:
    def it_should_return_true_when_stdin_is_not_a_tty(self, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=False)

        result = confirm_interactively("Continue?")

        assert result is True

    def it_should_delegate_to_typer_confirm_when_stdin_is_a_tty(self, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)
        mock_confirm = mocker.patch("gilt.cli.console.typer.confirm", return_value=True)

        result = confirm_interactively("Continue?")

        assert result is True
        mock_confirm.assert_called_once_with("Continue?")

    def it_should_return_false_when_user_declines(self, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)
        mocker.patch("gilt.cli.console.typer.confirm", return_value=False)

        result = confirm_interactively("Continue?")

        assert result is False


class DescribeDisplayCategoryChangeMatches:
    def _make_match(self, category=None, subcategory=None):
        t = Transaction(
            transaction_id="abcd1234abcd1234",
            date=date(2025, 3, 1),
            description="EXAMPLE UTILITY",
            amount=-50.0,
            currency="CAD",
            account_id="MYBANK_CHQ",
            category=category,
            subcategory=subcategory,
        )
        group = TransactionGroup(group_id=t.transaction_id, primary=t)
        return ("MYBANK_CHQ", group)

    def it_should_render_from_and_to_category_columns_with_fixed_from_label(self, mocker):
        mock_display = mocker.patch("gilt.cli.console.display_transaction_matches")
        match = self._make_match(category="Food", subcategory="Groceries")

        display_category_change_matches(
            "Test Table",
            "From",
            "→ To",
            [match],
            "Utilities:Electric",
            from_label="Food:Groceries",
        )

        call_kwargs = mock_display.call_args
        title, extra_columns, matches, row_fn = call_kwargs[0]
        assert title == "Test Table"
        assert extra_columns[0][0] == "From"
        assert extra_columns[1][0] == "→ To"
        row = row_fn(match)
        assert row[-2] == "Food:Groceries"
        assert row[-1] == "Utilities:Electric"

    def it_should_show_per_row_current_category_when_from_label_is_none(self, mocker):
        mock_display = mocker.patch("gilt.cli.console.display_transaction_matches")
        match = self._make_match(category="Food", subcategory="Groceries")

        display_category_change_matches(
            "Test Table",
            "Current Cat",
            "→ New Cat",
            [match],
            "Utilities:Electric",
        )

        _title, _cols, _matches, row_fn = mock_display.call_args[0]
        row = row_fn(match)
        assert row[-2] == "Food:Groceries"
        assert row[-1] == "Utilities:Electric"

    def it_should_show_dash_when_transaction_has_no_category(self, mocker):
        mock_display = mocker.patch("gilt.cli.console.display_transaction_matches")
        match = self._make_match()

        display_category_change_matches(
            "Test Table",
            "Current Cat",
            "→ New Cat",
            [match],
            "Utilities",
        )

        _title, _cols, _matches, row_fn = mock_display.call_args[0]
        row = row_fn(match)
        assert row[-2] == "—"
