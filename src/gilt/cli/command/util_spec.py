from __future__ import annotations

import sqlite3
from decimal import Decimal
from unittest.mock import Mock

from rich.table import Table

from gilt.cli.command.util import (
    create_transaction_table,
    display_transaction_matches,
    filter_by_account,
    filter_uncategorized,
    print_error,
    print_error_list,
    print_transaction_table,
    print_warning,
    require_event_sourcing,
    require_persistence_service,
    require_projections,
)
from gilt.model.events import TransactionImported
from gilt.services.categorization_persistence_service import CategorizationPersistenceService
from gilt.services.event_sourcing_service import EventSourcingReadyResult
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


class DescribeFilterUncategorized:
    def it_should_filter_uncategorized_rows(self):
        rows = [
            {"account_id": "ACC1", "category": "Food"},
            {"account_id": "ACC2", "category": None},
            {"account_id": "ACC3"},
        ]

        result = filter_uncategorized(rows)

        assert result == [{"account_id": "ACC2", "category": None}, {"account_id": "ACC3"}]

    def it_should_return_empty_when_all_categorized(self):
        rows = [
            {"account_id": "ACC1", "category": "Food"},
            {"account_id": "ACC2", "category": "Transport"},
        ]

        result = filter_uncategorized(rows)

        assert result == []


class DescribeFilterByAccount:
    def it_should_filter_by_account(self):
        rows = [
            {"account_id": "ACC1", "amount": -100},
            {"account_id": "ACC2", "amount": -200},
            {"account_id": "ACC1", "amount": -50},
        ]

        result = filter_by_account(rows, "ACC1")

        assert result == [{"account_id": "ACC1", "amount": -100}, {"account_id": "ACC1", "amount": -50}]

    def it_should_return_all_when_account_is_none(self):
        rows = [
            {"account_id": "ACC1", "amount": -100},
            {"account_id": "ACC2", "amount": -200},
        ]

        result = filter_by_account(rows, None)

        assert result == rows


class DescribePrintError:
    def it_should_print_error_with_red_prefix(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")

        print_error("something went wrong")

        mock_console.print.assert_called_once_with("[red]Error:[/] something went wrong")

    def it_should_include_the_message_verbatim(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")

        print_error("file not found: /data/foo.csv")

        args = mock_console.print.call_args[0][0]
        assert "file not found: /data/foo.csv" in args


class DescribePrintWarning:
    def it_should_print_warning_with_yellow_prefix(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")

        print_warning("deprecated feature used")

        mock_console.print.assert_called_once_with("[yellow]Warning:[/] deprecated feature used")

    def it_should_include_the_message_verbatim(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")

        print_warning("only 3 items found")

        args = mock_console.print.call_args[0][0]
        assert "only 3 items found" in args


class DescribePrintErrorList:
    def it_should_print_heading_and_bullets(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")

        print_error_list("Validation errors", ["field required", "value out of range"])

        calls = [c[0][0] for c in mock_console.print.call_args_list]
        assert calls[0] == "[red]Validation errors:[/]"
        assert calls[1] == "  • field required"
        assert calls[2] == "  • value out of range"

    def it_should_print_nothing_for_empty_list(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")

        print_error_list("No errors", [])

        calls = [c[0][0] for c in mock_console.print.call_args_list]
        assert len(calls) == 1
        assert calls[0] == "[red]No errors:[/]"


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
        assert headers == [
            "Account",
            "TxnID",
            "Date",
            "Description",
            "Amount",
            "Current Note",
            "→ New Note",
        ]

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


class DescribeDisplayTransactionMatches:
    def it_should_create_and_print_a_table_with_all_matches(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")
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
        mocker.patch("gilt.cli.command.util.console")
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
        mock_print_table = mocker.patch("gilt.cli.command.util.print_transaction_table")
        mocker.patch("gilt.cli.command.util.create_transaction_table")
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
        mock_console = mocker.patch("gilt.cli.command.util.console")

        display_transaction_matches("Test", [], [], lambda item: (str(item),))

        assert mock_console.print.called


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


class DescribeRequireEventSourcing:
    def it_should_return_ready_result_when_event_store_exists(self, tmp_path):
        ws = Workspace(root=tmp_path)
        ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
        # Create a real event store and projections
        ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
        store = EventStore(str(ws.event_store_path))
        store.append_event(
            TransactionImported(
                transaction_id="aaaa0001aaaa0001",
                transaction_date="2025-01-10",
                source_file="test.csv",
                source_account="TEST_CHQ",
                raw_description="SAMPLE STORE",
                amount=Decimal("-50.00"),
                currency="CAD",
                raw_data={},
            )
        )
        builder = ProjectionBuilder(ws.projections_path)
        builder.rebuild_from_scratch(store)

        result = require_event_sourcing(ws)

        assert result is not None
        assert result.ready is True
        assert result.event_store is not None
        assert result.projection_builder is not None

    def it_should_return_none_when_event_store_missing_with_csv_files(self, tmp_path, mocker):
        ws = Workspace(root=tmp_path)
        not_ready = EventSourcingReadyResult(ready=False, error="no_event_store", csv_files_count=2)
        mock_svc = mocker.patch("gilt.cli.command.util.EventSourcingService")
        mock_svc.return_value.ensure_ready.return_value = not_ready

        result = require_event_sourcing(ws)

        assert result is None

    def it_should_return_none_when_no_data_exists(self, tmp_path, mocker):
        ws = Workspace(root=tmp_path)
        not_ready = EventSourcingReadyResult(ready=False, error="no_data")
        mock_svc = mocker.patch("gilt.cli.command.util.EventSourcingService")
        mock_svc.return_value.ensure_ready.return_value = not_ready

        result = require_event_sourcing(ws)

        assert result is None


class DescribeRequirePersistenceService:
    def it_should_return_categorization_persistence_service(self, tmp_path):
        event_store = Mock()
        projection_builder = Mock()
        workspace = Workspace(root=tmp_path)

        result = require_persistence_service(event_store, projection_builder, workspace)

        assert isinstance(result, CategorizationPersistenceService)
