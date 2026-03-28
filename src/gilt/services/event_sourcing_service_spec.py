from __future__ import annotations

"""
Specs for EventSourcingService — infrastructure setup for event store and projections.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.model.events import TransactionImported
from gilt.services.event_sourcing_service import (
    EventSourcingService,
    EventStoreStatus,
    ProjectionStatus,
)
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def _append_transaction_event(store: EventStore, *, txn_id: str, account: str) -> None:
    """Append a minimal TransactionImported event to the store."""
    event = TransactionImported(
        transaction_id=txn_id,
        transaction_date="2025-01-10",
        source_file="mybank_export.csv",
        source_account=account,
        raw_description="SAMPLE STORE",
        amount=Decimal("-50.00"),
        currency="CAD",
        raw_data={},
    )
    store.append_event(event)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class DescribeEventSourcingServicePathResolution:
    """Specs for how paths are resolved depending on constructor arguments."""

    def it_should_use_workspace_paths_when_workspace_given(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            service = EventSourcingService(workspace=ws)
            assert service.event_store_path == ws.event_store_path
            assert service.projections_path == ws.projections_path

    def it_should_prefer_explicit_paths_over_workspace_paths(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            explicit_es = Path(tmpdir) / "custom_events.db"
            explicit_proj = Path(tmpdir) / "custom_projections.db"
            service = EventSourcingService(
                event_store_path=explicit_es,
                projections_path=explicit_proj,
                workspace=ws,
            )
            assert service.event_store_path == explicit_es
            assert service.projections_path == explicit_proj

    def it_should_raise_when_no_workspace_or_paths_provided(self):
        import pytest

        with pytest.raises(ValueError, match="workspace"):
            EventSourcingService()


# ---------------------------------------------------------------------------
# check_event_store_status
# ---------------------------------------------------------------------------


class DescribeCheckEventStoreStatus:
    """Specs for event store existence check."""

    def it_should_report_not_exists_when_db_file_absent(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            service = EventSourcingService(workspace=ws)
            status = service.check_event_store_status()
            assert isinstance(status, EventStoreStatus)
            assert status.exists is False
            assert status.path == ws.event_store_path

    def it_should_report_exists_after_event_store_is_created(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            # Touch the DB by creating an event store
            store = EventStore(str(ws.event_store_path))
            _append_transaction_event(store, txn_id="aaaa0001aaaa0001", account="MYBANK_CHQ")

            service = EventSourcingService(workspace=ws)
            status = service.check_event_store_status()
            assert status.exists is True

    def it_should_count_csv_files_in_data_dir_when_event_store_missing(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            data_dir = ws.ledger_data_dir
            data_dir.mkdir(parents=True, exist_ok=True)
            # Create two synthetic CSV files
            (data_dir / "MYBANK_CHQ.csv").write_text("header\n", encoding="utf-8")
            (data_dir / "MYBANK_CC.csv").write_text("header\n", encoding="utf-8")

            service = EventSourcingService(workspace=ws)
            status = service.check_event_store_status(data_dir=data_dir)
            assert status.csv_files_count == 2

    def it_should_not_count_csv_files_when_event_store_exists(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            EventStore(str(ws.event_store_path))  # creates the DB file

            data_dir = ws.ledger_data_dir
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "MYBANK_CHQ.csv").write_text("header\n", encoding="utf-8")

            service = EventSourcingService(workspace=ws)
            status = service.check_event_store_status(data_dir=data_dir)
            # csv_files_count only populated when event store is missing
            assert status.csv_files_count is None


# ---------------------------------------------------------------------------
# check_projection_status
# ---------------------------------------------------------------------------


class DescribeCheckProjectionStatus:
    """Specs for projection existence and freshness check."""

    def it_should_report_not_exists_when_projections_db_absent(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            store = EventStore(str(ws.event_store_path))

            service = EventSourcingService(workspace=ws)
            status = service.check_projection_status(store)
            assert isinstance(status, ProjectionStatus)
            assert status.exists is False

    def it_should_report_up_to_date_when_projections_match_events(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            store = EventStore(str(ws.event_store_path))
            _append_transaction_event(store, txn_id="bbbb0001bbbb0001", account="MYBANK_CHQ")

            builder = ProjectionBuilder(ws.projections_path)
            builder.rebuild_from_scratch(store)

            service = EventSourcingService(workspace=ws)
            status = service.check_projection_status(store)
            assert status.exists is True
            assert status.is_outdated is False
            assert status.events_to_process == 0

    def it_should_report_outdated_when_new_events_added_after_build(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            store = EventStore(str(ws.event_store_path))
            _append_transaction_event(store, txn_id="cccc0001cccc0001", account="MYBANK_CHQ")

            builder = ProjectionBuilder(ws.projections_path)
            builder.rebuild_from_scratch(store)

            # Add a new event AFTER the projections were built
            _append_transaction_event(store, txn_id="cccc0002cccc0002", account="MYBANK_CHQ")

            service = EventSourcingService(workspace=ws)
            status = service.check_projection_status(store)
            assert status.is_outdated is True
            assert status.events_to_process > 0


# ---------------------------------------------------------------------------
# get_event_store / get_projection_builder
# ---------------------------------------------------------------------------


class DescribeGetEventStore:
    """Specs for event store factory method."""

    def it_should_return_an_event_store_instance(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            service = EventSourcingService(workspace=ws)
            store = service.get_event_store()
            assert isinstance(store, EventStore)

    def it_should_create_db_file_on_get(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            service = EventSourcingService(workspace=ws)
            assert not ws.event_store_path.exists()
            service.get_event_store()
            assert ws.event_store_path.exists()


class DescribeGetProjectionBuilder:
    """Specs for projection builder factory method."""

    def it_should_return_a_projection_builder_instance(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.projections_path.parent.mkdir(parents=True, exist_ok=True)
            service = EventSourcingService(workspace=ws)
            builder = service.get_projection_builder()
            assert isinstance(builder, ProjectionBuilder)


# ---------------------------------------------------------------------------
# ensure_projections_up_to_date
# ---------------------------------------------------------------------------


class DescribeEnsureProjectionsUpToDate:
    """Specs for the ensure-up-to-date helper."""

    def it_should_return_zero_when_projections_already_current(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            store = EventStore(str(ws.event_store_path))
            _append_transaction_event(store, txn_id="dddd0001dddd0001", account="MYBANK_CHQ")

            builder = ProjectionBuilder(ws.projections_path)
            builder.rebuild_from_scratch(store)

            service = EventSourcingService(workspace=ws)
            result = service.ensure_projections_up_to_date(store, builder)
            assert result == 0

    def it_should_return_positive_count_when_projections_are_rebuilt(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            store = EventStore(str(ws.event_store_path))
            _append_transaction_event(store, txn_id="eeee0001eeee0001", account="MYBANK_CHQ")

            # No projections exist yet
            service = EventSourcingService(workspace=ws)
            builder = service.get_projection_builder()
            result = service.ensure_projections_up_to_date(store, builder)
            assert result > 0

    def it_should_use_incremental_rebuild_when_projections_are_outdated(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            store = EventStore(str(ws.event_store_path))
            _append_transaction_event(store, txn_id="ffff0001ffff0001", account="MYBANK_CHQ")

            builder = ProjectionBuilder(ws.projections_path)
            builder.rebuild_from_scratch(store)

            # Add a second event to make projections outdated
            _append_transaction_event(store, txn_id="ffff0002ffff0002", account="MYBANK_CC")

            service = EventSourcingService(workspace=ws)
            result = service.ensure_projections_up_to_date(store, builder)
            assert result > 0
