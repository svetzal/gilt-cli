from __future__ import annotations

from decimal import Decimal

from gilt.cli.loaders import (
    load_account_transactions,
    load_all_transactions,
    load_filtered_transactions,
)
from gilt.model.events import TransactionImported
from gilt.services.transaction_query_service import TransactionFilter
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


class DescribeLoadAccountTransactions:
    def it_should_return_none_when_projections_missing(self, tmp_path):
        workspace = Workspace(root=tmp_path)

        result = load_account_transactions(workspace, None)

        assert result is None

    def it_should_return_none_and_print_error_when_no_transactions_for_account(
        self, tmp_path, mocker
    ):
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
        mock_console = mocker.patch("gilt.cli.console.console")

        result = load_account_transactions(workspace, "NONEXISTENT_ACCT")

        assert result is None
        mock_console.print.assert_called()
        args = mock_console.print.call_args[0][0]
        assert "NONEXISTENT_ACCT" in args

    def it_should_return_filtered_rows_on_happy_path(self, tmp_path):
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


class DescribeLoadAllTransactions:
    def it_should_return_none_when_projections_missing(self, tmp_path):
        workspace = Workspace(root=tmp_path)

        result = load_all_transactions(workspace, include_duplicates=False)

        assert result is None

    def it_should_return_transaction_list_when_projections_exist(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        store = EventStore(str(workspace.event_store_path))
        store.append_event(
            TransactionImported(
                transaction_id="aabbccdd11223344",
                transaction_date="2025-01-01",
                source_file="test.csv",
                source_account="TEST",
                raw_description="Test Transaction",
                amount=Decimal("-100.00"),
                currency="CAD",
                raw_data={},
            )
        )
        builder = ProjectionBuilder(workspace.projections_path)
        builder.build_from_scratch(store)

        result = load_all_transactions(workspace, include_duplicates=False)

        assert result is not None
        assert len(result) == 1
        assert result[0].transaction_id == "aabbccdd11223344"


class DescribeLoadFilteredTransactions:
    def it_should_return_none_when_projections_missing(self, tmp_path):
        workspace = Workspace(root=tmp_path)

        result = load_filtered_transactions(workspace, TransactionFilter())

        assert result is None

    def it_should_return_filtered_transactions_from_projections(self, tmp_path):
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

        result = load_filtered_transactions(workspace, TransactionFilter(account_id="MYBANK_CHQ"))

        assert result is not None
        assert len(result) == 1
        assert result[0].transaction_id == "aaaa0001aaaa0001"
        assert result[0].account_id == "MYBANK_CHQ"
