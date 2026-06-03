from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

from rich.table import Table

from gilt.cli.command.util import (
    apply_categorization_updates,
    build_transaction_table,
    display_transaction_matches,
    find_by_account,
    find_by_id_prefix,
    find_matches_by_criteria,
    find_uncategorized,
    fmt_colored_amount,
    load_account_transactions,
    load_event_store,
    load_filtered_transactions,
    parse_category_path,
    print_error,
    print_error_list,
    print_transaction_table,
    print_warning,
    require_event_sourcing,
    require_persistence_service,
    require_projections,
    search_by_criteria,
    validate_single_vs_batch_mode,
)
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.events import TransactionImported
from gilt.services.categorization_persistence_service import (
    CategorizationPersistenceResult,
    CategorizationPersistenceService,
    CategorizationUpdate,
)
from gilt.services.event_sourcing_service import EventSourcingReadyResult
from gilt.services.transaction_operations_service import (
    BatchPreview,
    MatchResult,
    SearchCriteria,
    TransactionOperationsService,
)
from gilt.services.transaction_query_service import TransactionFilter
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


class DescribeFmtColoredAmount:
    def it_should_return_red_markup_for_negative_amounts(self):
        result = fmt_colored_amount(-42.50)

        assert result == "[red]$-42.50[/]"

    def it_should_return_green_markup_for_positive_amounts(self):
        result = fmt_colored_amount(100.00)

        assert result == "[green]$100.00[/]"

    def it_should_return_plain_string_for_zero(self):
        result = fmt_colored_amount(0.0)

        assert result == "$0.00"

    def it_should_add_bold_to_red_markup_when_bold_is_true(self):
        result = fmt_colored_amount(-42.50, bold=True)

        assert result == "[red bold]$-42.50[/]"

    def it_should_add_bold_to_green_markup_when_bold_is_true(self):
        result = fmt_colored_amount(100.00, bold=True)

        assert result == "[green bold]$100.00[/]"

    def it_should_wrap_zero_in_bold_markup_when_bold_is_true(self):
        result = fmt_colored_amount(0.0, bold=True)

        assert result == "[bold]$0.00[/]"

    def it_should_respect_custom_prefix(self):
        result = fmt_colored_amount(-10.0, prefix="")

        assert result == "[red]-10.00[/]"


class DescribeFilterUncategorized:
    def it_should_filter_uncategorized_rows(self):
        rows = [
            {"account_id": "ACC1", "category": "Food"},
            {"account_id": "ACC2", "category": None},
            {"account_id": "ACC3"},
        ]

        result = find_uncategorized(rows)

        assert result == [{"account_id": "ACC2", "category": None}, {"account_id": "ACC3"}]

    def it_should_return_empty_when_all_categorized(self):
        rows = [
            {"account_id": "ACC1", "category": "Food"},
            {"account_id": "ACC2", "category": "Transport"},
        ]

        result = find_uncategorized(rows)

        assert result == []


class DescribeFilterByAccount:
    def it_should_filter_by_account(self):
        rows = [
            {"account_id": "ACC1", "amount": -100},
            {"account_id": "ACC2", "amount": -200},
            {"account_id": "ACC1", "amount": -50},
        ]

        result = find_by_account(rows, "ACC1")

        assert result == [
            {"account_id": "ACC1", "amount": -100},
            {"account_id": "ACC1", "amount": -50},
        ]

    def it_should_return_all_when_account_is_none(self):
        rows = [
            {"account_id": "ACC1", "amount": -100},
            {"account_id": "ACC2", "amount": -200},
        ]

        result = find_by_account(rows, None)

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

        table = build_transaction_table("Matched Transactions", extra_columns)

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
        table = build_transaction_table("Test", [])

        cols = table.columns
        assert cols[0].style == "cyan"
        assert cols[1].style == "blue"
        assert cols[4].style == "yellow"

    def it_should_apply_right_justify_to_amount_column(self):
        table = build_transaction_table("Test", [])

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
        mocker.patch("gilt.cli.command.util.build_transaction_table")
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
        builder.build_from_scratch(store)

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
        ready = Mock(spec=EventSourcingReadyResult)
        workspace = Workspace(root=tmp_path)

        result = require_persistence_service(ready, workspace)

        assert isinstance(result, CategorizationPersistenceService)


def _make_group(
    transaction_id: str, description: str = "Test", amount: float = -10.0
) -> TransactionGroup:
    return TransactionGroup(
        group_id=transaction_id,
        primary=Transaction(
            transaction_id=transaction_id,
            date=date(2025, 1, 1),
            description=description,
            amount=amount,
            currency="CAD",
            account_id="TEST_CHQ",
        ),
    )


class DescribeValidateSingleVsBatchMode:
    def it_should_return_true_for_single_mode(self, mocker):
        mocker.patch("gilt.cli.command.util.console")

        result = validate_single_vs_batch_mode("abcd1234", None, None, None)

        assert result is True

    def it_should_return_false_for_batch_mode_with_description(self, mocker):
        mocker.patch("gilt.cli.command.util.console")

        result = validate_single_vs_batch_mode(None, "SAMPLE STORE", None, None)

        assert result is False

    def it_should_return_false_for_batch_mode_with_desc_prefix(self, mocker):
        mocker.patch("gilt.cli.command.util.console")

        result = validate_single_vs_batch_mode(None, None, "SAMPLE", None)

        assert result is False

    def it_should_return_false_for_batch_mode_with_pattern(self, mocker):
        mocker.patch("gilt.cli.command.util.console")

        result = validate_single_vs_batch_mode(None, None, None, r"\d+")

        assert result is False

    def it_should_return_none_when_no_mode_specified(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")

        result = validate_single_vs_batch_mode(None, None, None, None)

        assert result is None
        mock_console.print.assert_called_once()

    def it_should_return_none_when_multiple_modes_specified(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")

        result = validate_single_vs_batch_mode("abcd1234", "SAMPLE STORE", None, None)

        assert result is None
        mock_console.print.assert_called_once()

    def it_should_print_error_message_on_failure(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")

        validate_single_vs_batch_mode(None, None, None, None)

        args = mock_console.print.call_args[0][0]
        assert "--txid" in args
        assert "--description" in args


class DescribeResolveIdPrefix:
    def it_should_return_error_string_when_prefix_too_short(self):
        service = Mock(spec=TransactionOperationsService)
        groups = [_make_group("abcd1234abcd1234")]

        result = find_by_id_prefix(service, "abc", groups)

        assert isinstance(result, str)
        assert "8 characters" in result
        service.find_by_id_prefix.assert_not_called()

    def it_should_return_error_string_when_not_found(self):
        service = Mock(spec=TransactionOperationsService)
        service.find_by_id_prefix.return_value = MatchResult(type="not_found", matches=[])
        groups = [_make_group("abcd1234abcd1234")]

        result = find_by_id_prefix(service, "zzzzzzzz", groups)

        assert isinstance(result, str)
        assert "No transaction found" in result

    def it_should_return_error_string_when_ambiguous(self):
        g1 = _make_group("abcd1234abcd1234", description="First")
        g2 = _make_group("abcd1234eeff5566", description="Second")
        service = Mock(spec=TransactionOperationsService)
        service.find_by_id_prefix.return_value = MatchResult(type="ambiguous", matches=[g1, g2])

        result = find_by_id_prefix(service, "abcd1234", [g1, g2])

        assert isinstance(result, str)
        assert "Ambiguous" in result
        assert "2" in result

    def it_should_return_matched_groups_on_exact_match(self):
        group = _make_group("abcd1234abcd1234")
        service = Mock(spec=TransactionOperationsService)
        service.find_by_id_prefix.return_value = MatchResult(
            type="match", transaction=group, matches=[]
        )

        result = find_by_id_prefix(service, "abcd1234", [group])

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] is group

    def it_should_normalize_prefix_to_lowercase(self):
        group = _make_group("abcd1234abcd1234")
        service = Mock(spec=TransactionOperationsService)
        service.find_by_id_prefix.return_value = MatchResult(
            type="match", transaction=group, matches=[]
        )

        find_by_id_prefix(service, "ABCD1234", [group])

        call_prefix = service.find_by_id_prefix.call_args[0][0]
        assert call_prefix == "abcd1234"


class DescribeSearchByCriteria:
    def it_should_return_preview_on_valid_search(self, mocker):
        mocker.patch("gilt.cli.command.util.console")
        group = _make_group("abcd1234abcd1234", description="SAMPLE STORE")
        criteria = SearchCriteria(description="SAMPLE STORE")
        preview = BatchPreview(
            matched_groups=[group],
            total_count=1,
            criteria=criteria,
        )
        service = Mock(spec=TransactionOperationsService)
        service.find_by_criteria.return_value = preview

        result = search_by_criteria(service, criteria, [group], None)

        assert result is preview

    def it_should_return_none_on_invalid_pattern(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")
        criteria = SearchCriteria(pattern=r"[invalid")
        preview = BatchPreview(
            matched_groups=[],
            total_count=0,
            criteria=criteria,
            invalid_pattern=True,
        )
        service = Mock(spec=TransactionOperationsService)
        service.find_by_criteria.return_value = preview

        result = search_by_criteria(service, criteria, [], r"[invalid")

        assert result is None
        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0][0]
        assert "Invalid regex pattern" in args

    def it_should_print_sign_insensitive_note_when_applicable(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")
        group = _make_group("abcd1234abcd1234", description="SAMPLE STORE", amount=-10.0)
        criteria = SearchCriteria(description="SAMPLE STORE", amount=10.0)
        preview = BatchPreview(
            matched_groups=[group],
            total_count=1,
            criteria=criteria,
            used_sign_insensitive=True,
        )
        service = Mock(spec=TransactionOperationsService)
        service.find_by_criteria.return_value = preview

        result = search_by_criteria(service, criteria, [group], None)

        assert result is preview
        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0][0]
        assert "absolute amount" in args

    def it_should_not_print_note_when_sign_sensitive_match(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")
        group = _make_group("abcd1234abcd1234", description="SAMPLE STORE", amount=-10.0)
        criteria = SearchCriteria(description="SAMPLE STORE", amount=-10.0)
        preview = BatchPreview(
            matched_groups=[group],
            total_count=1,
            criteria=criteria,
            used_sign_insensitive=False,
        )
        service = Mock(spec=TransactionOperationsService)
        service.find_by_criteria.return_value = preview

        result = search_by_criteria(service, criteria, [group], None)

        assert result is preview
        mock_console.print.assert_not_called()


class DescribeFindMatchesByCriteria:
    def it_should_accumulate_pairs_across_multiple_accounts(self, mocker):
        mocker.patch("gilt.cli.command.util.console")
        g1 = _make_group("aaaa0001aaaa0001", description="SAMPLE STORE")
        g2 = _make_group("bbbb0002bbbb0002", description="ACME CORP")
        groups_by_account = {"ACC1": [g1], "ACC2": [g2]}
        criteria = SearchCriteria(description="SAMPLE STORE")
        service = Mock(spec=TransactionOperationsService)
        service.find_transaction_targets.side_effect = [[g1], [g2]]

        result = find_matches_by_criteria(groups_by_account, criteria, service)

        assert result == [("ACC1", g1), ("ACC2", g2)]

    def it_should_return_none_and_print_error_when_service_returns_nonempty_string(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")
        g1 = _make_group("aaaa0001aaaa0001")
        groups_by_account = {"ACC1": [g1]}
        criteria = SearchCriteria(description="SAMPLE STORE")
        service = Mock(spec=TransactionOperationsService)
        service.find_transaction_targets.return_value = "Invalid regex pattern"

        result = find_matches_by_criteria(groups_by_account, criteria, service)

        assert result is None
        mock_console.print.assert_called_once()

    def it_should_return_none_silently_when_service_returns_empty_string(self, mocker):
        mock_console = mocker.patch("gilt.cli.command.util.console")
        g1 = _make_group("aaaa0001aaaa0001")
        groups_by_account = {"ACC1": [g1]}
        criteria = SearchCriteria(description="SAMPLE STORE")
        service = Mock(spec=TransactionOperationsService)
        service.find_transaction_targets.return_value = ""

        result = find_matches_by_criteria(groups_by_account, criteria, service)

        assert result is None
        mock_console.print.assert_not_called()

    def it_should_forward_txid_to_service(self, mocker):
        mocker.patch("gilt.cli.command.util.console")
        g1 = _make_group("aaaa0001aaaa0001")
        groups_by_account = {"ACC1": [g1]}
        criteria = SearchCriteria()
        service = Mock(spec=TransactionOperationsService)
        service.find_transaction_targets.return_value = [g1]

        find_matches_by_criteria(groups_by_account, criteria, service, txid="aaaa0001")

        service.find_transaction_targets.assert_called_once_with(
            [g1],
            txid="aaaa0001",
            description=None,
            desc_prefix=None,
            pattern=None,
            amount=None,
        )


class DescribeLoadAccountTransactions:
    def it_should_return_none_when_projections_missing(self, tmp_path):
        workspace = Workspace(root=tmp_path)

        result = load_account_transactions(workspace, None)

        assert result is None

    def it_should_return_none_and_print_error_when_no_transactions_for_account(
        self, tmp_path, mocker
    ):
        from decimal import Decimal

        from gilt.model.events import TransactionImported
        from gilt.storage.event_store import EventStore
        from gilt.storage.projection import ProjectionBuilder

        workspace = Workspace(root=tmp_path)
        workspace.event_store_path.parent.mkdir(parents=True, exist_ok=True)
        store = EventStore(str(workspace.event_store_path))
        store.append_event(
            TransactionImported(
                transaction_id="aaaa0001aaaa0001",
                transaction_date="2025-01-10",
                source_file="test.csv",
                source_account="MYBANK_CHQ",
                raw_description="EXAMPLE UTILITY",
                amount=Decimal("-50.00"),
                currency="CAD",
                raw_data={},
            )
        )
        ProjectionBuilder(workspace.projections_path).build_from_scratch(store)
        mock_console = mocker.patch("gilt.cli.command.util.console")

        result = load_account_transactions(workspace, "NONEXISTENT_ACCT")

        assert result is None
        mock_console.print.assert_called()
        args = mock_console.print.call_args[0][0]
        assert "NONEXISTENT_ACCT" in args

    def it_should_return_filtered_rows_on_happy_path(self, tmp_path):
        from decimal import Decimal

        from gilt.model.events import TransactionImported
        from gilt.storage.event_store import EventStore
        from gilt.storage.projection import ProjectionBuilder

        workspace = Workspace(root=tmp_path)
        workspace.event_store_path.parent.mkdir(parents=True, exist_ok=True)
        store = EventStore(str(workspace.event_store_path))
        store.append_event(
            TransactionImported(
                transaction_id="aaaa0001aaaa0001",
                transaction_date="2025-01-10",
                source_file="test.csv",
                source_account="MYBANK_CHQ",
                raw_description="EXAMPLE UTILITY",
                amount=Decimal("-50.00"),
                currency="CAD",
                raw_data={},
            )
        )
        store.append_event(
            TransactionImported(
                transaction_id="bbbb0002bbbb0002",
                transaction_date="2025-01-11",
                source_file="test.csv",
                source_account="MYBANK_CC",
                raw_description="SAMPLE STORE",
                amount=Decimal("-20.00"),
                currency="CAD",
                raw_data={},
            )
        )
        ProjectionBuilder(workspace.projections_path).build_from_scratch(store)

        result = load_account_transactions(workspace, "MYBANK_CHQ")

        assert result is not None
        assert len(result) == 1
        assert result[0]["account_id"] == "MYBANK_CHQ"


class DescribeApplyCategorizationUpdates:
    def it_should_call_persist_categorizations_with_updates(self, tmp_path, mocker):
        ready = Mock(spec=EventSourcingReadyResult)
        workspace = Workspace(root=tmp_path)
        updates = [
            CategorizationUpdate(
                transaction_id="aaaa0001aaaa0001",
                account_id="MYBANK_CHQ",
                category="Food",
                subcategory=None,
                source="user",
                confidence=1.0,
            )
        ]
        expected_result = CategorizationPersistenceResult(transactions_updated=1, events_emitted=1)
        mock_svc = mocker.patch("gilt.cli.command.util.require_persistence_service")
        mock_svc.return_value.persist_categorizations.return_value = expected_result

        result = apply_categorization_updates(ready, workspace, updates)

        mock_svc.return_value.persist_categorizations.assert_called_once_with(updates)
        assert result is expected_result


class DescribeLoadEventStore:
    def it_should_return_none_when_event_store_missing(self, tmp_path):
        workspace = Workspace(root=tmp_path)

        result = load_event_store(workspace)

        assert result is None

    def it_should_return_event_store_when_it_exists(self, tmp_path):
        from gilt.storage.event_store import EventStore

        workspace = Workspace(root=tmp_path)
        workspace.event_store_path.parent.mkdir(parents=True, exist_ok=True)
        EventStore(str(workspace.event_store_path))

        result = load_event_store(workspace)

        assert result is not None


class DescribeParseCategoryPath:
    def it_should_split_colon_syntax_into_category_and_subcategory(self):
        cat, subcat, warning = parse_category_path("Food:Groceries")

        assert cat == "Food"
        assert subcat == "Groceries"
        assert warning is None

    def it_should_return_empty_cat_for_empty_input(self):
        cat, subcat, warning = parse_category_path("")

        assert cat == ""
        assert subcat is None
        assert warning is None

    def it_should_return_warning_when_subcategory_conflicts_with_colon_syntax(self):
        cat, subcat, warning = parse_category_path("Food:Groceries", subcategory="Dining")

        assert cat == "Food"
        assert subcat == "Groceries"
        assert warning is not None
        assert "--subcategory" in warning or "subcategory" in warning.lower()

    def it_should_prefer_colon_subcat_over_separate_subcategory_arg(self):
        cat, subcat, warning = parse_category_path("Food:Groceries", subcategory="Dining")

        assert subcat == "Groceries"

    def it_should_accept_subcategory_when_no_colon_in_category(self):
        cat, subcat, warning = parse_category_path("Food", subcategory="Groceries")

        assert cat == "Food"
        assert subcat == "Groceries"
        assert warning is None

    def it_should_return_category_only_when_no_colon_and_no_subcategory(self):
        cat, subcat, warning = parse_category_path("Food")

        assert cat == "Food"
        assert subcat is None
        assert warning is None


class DescribeLoadFilteredTransactions:
    def it_should_return_none_when_projections_missing(self, tmp_path):
        workspace = Workspace(root=tmp_path)

        result = load_filtered_transactions(workspace, TransactionFilter())

        assert result is None

    def it_should_return_filtered_transactions_from_projections(self, tmp_path):
        from decimal import Decimal

        from gilt.model.events import TransactionImported
        from gilt.services.transaction_query_service import TransactionFilter
        from gilt.storage.event_store import EventStore
        from gilt.storage.projection import ProjectionBuilder

        workspace = Workspace(root=tmp_path)
        workspace.event_store_path.parent.mkdir(parents=True, exist_ok=True)
        store = EventStore(str(workspace.event_store_path))
        store.append_event(
            TransactionImported(
                transaction_id="aaaa0001aaaa0001",
                transaction_date="2025-03-10",
                source_file="test.csv",
                source_account="MYBANK_CHQ",
                raw_description="EXAMPLE UTILITY",
                amount=Decimal("-75.00"),
                currency="CAD",
                raw_data={},
            )
        )
        store.append_event(
            TransactionImported(
                transaction_id="bbbb0002bbbb0002",
                transaction_date="2025-04-15",
                source_file="test.csv",
                source_account="MYBANK_CC",
                raw_description="SAMPLE STORE",
                amount=Decimal("-30.00"),
                currency="CAD",
                raw_data={},
            )
        )
        builder = ProjectionBuilder(workspace.projections_path)
        builder.build_from_scratch(store)

        result = load_filtered_transactions(
            workspace, TransactionFilter(account_id="MYBANK_CHQ")
        )

        assert result is not None
        assert len(result) == 1
        assert result[0].transaction_id == "aaaa0001aaaa0001"
        assert result[0].account_id == "MYBANK_CHQ"
