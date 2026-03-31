from __future__ import annotations

import sqlite3

from rich.table import Table

from gilt.cli.command.util import (
    create_transaction_table,
    print_transaction_table,
    require_projections,
)
from gilt.workspace import Workspace


class DescribeCreateTransactionTable:
    def it_should_create_table_with_base_columns_and_extras(self):
        extra_columns = [
            ("Current Note", {"style": "dim"}),
            ("→ New Note", {"style": "green"}),
        ]

        table = create_transaction_table("Matched Transactions", extra_columns)

        assert isinstance(table, Table)
        assert len(table.columns) == 7
        headers = [col.header for col in table.columns]
        assert headers == ["Account", "TxnID", "Date", "Description", "Amount", "Current Note", "→ New Note"]

    def it_should_apply_correct_styles_to_base_columns(self):
        table = create_transaction_table("Test", [])

        cols = table.columns
        assert cols[0].style == "cyan"
        assert cols[1].style == "blue"
        assert cols[4].style == "yellow"

    def it_should_apply_right_justify_to_amount_column(self):
        table = create_transaction_table("Test", [])

        amount_col = table.columns[4]
        assert amount_col.justify == "right"


class DescribePrintTransactionTable:
    def it_should_print_overflow_message_when_exceeding_limit(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")
        table = Table()
        for _ in range(55):
            table.add_row("a")

        print_transaction_table(table, total_count=55, display_limit=50)

        overflow_call = mock_console.print.call_args_list[-1]
        assert "5 more" in str(overflow_call)

    def it_should_not_print_overflow_message_when_at_limit(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")
        table = Table()
        for _ in range(50):
            table.add_row("a")

        print_transaction_table(table, total_count=50, display_limit=50)

        calls = [str(c) for c in mock_console.print.call_args_list]
        assert not any("more" in c for c in calls)

    def it_should_not_print_overflow_message_when_below_limit(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")
        table = Table()
        for _ in range(10):
            table.add_row("a")

        print_transaction_table(table, total_count=10, display_limit=50)

        calls = [str(c) for c in mock_console.print.call_args_list]
        assert not any("more" in c for c in calls)


class DescribeRequireProjections:
    def it_should_return_projection_builder_when_db_exists(self, tmp_path):
        projections_path = tmp_path / "data" / "projections.db"
        projections_path.parent.mkdir(parents=True)
        sqlite3.connect(projections_path).close()
        workspace = Workspace(root=tmp_path)

        result = require_projections(workspace)

        assert result is not None

    def it_should_return_none_when_db_is_missing(self, tmp_path, capsys):
        workspace = Workspace(root=tmp_path)

        result = require_projections(workspace)

        assert result is None

    def it_should_print_error_message_when_db_is_missing(self, tmp_path, capsys):
        workspace = Workspace(root=tmp_path)

        require_projections(workspace)

        # Rich console writes to stdout; capture it
        captured = capsys.readouterr()
        assert "rebuild-projections" in captured.out
