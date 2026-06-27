from __future__ import annotations

import sqlite3
from decimal import Decimal
from unittest.mock import Mock

import pytest

from gilt.cli.command._errors import CommandAbort
from gilt.cli.event_sourcing_bootstrap import (
    load_event_store,
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

        with pytest.raises(CommandAbort):
            require_projections(workspace)

    def it_should_print_error_message_when_db_is_missing(self, tmp_path, capsys):
        workspace = Workspace(root=tmp_path)

        with pytest.raises(CommandAbort):
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
        mock_svc = mocker.patch("gilt.cli.event_sourcing_bootstrap.EventSourcingService")
        mock_svc.return_value.ensure_ready.return_value = not_ready

        with pytest.raises(CommandAbort):
            require_event_sourcing(ws)

    def it_should_return_none_when_no_data_exists(self, tmp_path, mocker):
        ws = Workspace(root=tmp_path)
        not_ready = EventSourcingReadyResult(ready=False, error="no_data")
        mock_svc = mocker.patch("gilt.cli.event_sourcing_bootstrap.EventSourcingService")
        mock_svc.return_value.ensure_ready.return_value = not_ready

        with pytest.raises(CommandAbort):
            require_event_sourcing(ws)


class DescribeRequirePersistenceService:
    def it_should_return_categorization_persistence_service(self, tmp_path):
        ready = Mock(spec=EventSourcingReadyResult)
        workspace = Workspace(root=tmp_path)

        result = require_persistence_service(ready, workspace)

        assert isinstance(result, CategorizationPersistenceService)


class DescribeLoadEventStore:
    def it_should_return_none_when_event_store_missing(self, tmp_path):
        workspace = Workspace(root=tmp_path)

        result = load_event_store(workspace)

        assert result is None

    def it_should_return_event_store_when_it_exists(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        workspace.event_store_path.parent.mkdir(parents=True, exist_ok=True)
        EventStore(str(workspace.event_store_path))

        result = load_event_store(workspace)

        assert result is not None
