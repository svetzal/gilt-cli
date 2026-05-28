from __future__ import annotations

"""
Tests for diagnose_duplicates CLI command.
"""

import sqlite3
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.cli.command.diagnose_duplicates import run
from gilt.model.events import TransactionImported
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def _build_minimal_workspace(tmp_path: Path) -> tuple[Workspace, ProjectionBuilder, EventStore]:
    """Create a workspace with event store and projections for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "accounts").mkdir(parents=True, exist_ok=True)

    events_path = data_dir / "events.db"
    projections_path = data_dir / "projections.db"

    event_store = EventStore(str(events_path))
    projection_builder = ProjectionBuilder(projections_path)

    workspace = Workspace(root=tmp_path)
    return workspace, projection_builder, event_store


def _import_txn(event_store: EventStore, txn_id: str, desc: str = "EXAMPLE UTILITY") -> None:
    event_store.append_event(
        TransactionImported(
            transaction_date="2025-01-15",
            transaction_id=txn_id,
            source_file="test.csv",
            source_account="MYBANK_CHQ",
            raw_description=desc,
            amount=Decimal("-50.00"),
            currency="CAD",
            raw_data={},
        )
    )


class DescribeDiagnose_DuplicatesCommand:
    def it_should_return_zero_when_no_issues_found(self):
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workspace, projection_builder, event_store = _build_minimal_workspace(tmp_path)

            _import_txn(event_store, "aaaa000000000001")
            _import_txn(event_store, "bbbb000000000002")
            projection_builder.build_from_scratch(event_store)

            # Mark bbbb as duplicate of aaaa via direct SQL (well-formed state)
            conn = sqlite3.connect(projection_builder.db_path)
            try:
                conn.execute(
                    "UPDATE transaction_projections SET is_duplicate=1, primary_transaction_id=? "
                    "WHERE transaction_id=?",
                    ("aaaa000000000001", "bbbb000000000002"),
                )
                conn.commit()
            finally:
                conn.close()

            rc = run(workspace=workspace)
            assert rc == 0

    def it_should_return_one_when_orphan_group_present(self):
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workspace, projection_builder, event_store = _build_minimal_workspace(tmp_path)

            _import_txn(event_store, "aaaa000000000001", "SAMPLE STORE A")
            _import_txn(event_store, "bbbb000000000002", "SAMPLE STORE B")
            projection_builder.build_from_scratch(event_store)

            # Corrupt: both rows is_duplicate=1 (orphan cycle)
            conn = sqlite3.connect(projection_builder.db_path)
            try:
                conn.execute(
                    "UPDATE transaction_projections SET is_duplicate=1, primary_transaction_id=? "
                    "WHERE transaction_id=?",
                    ("bbbb000000000002", "aaaa000000000001"),
                )
                conn.execute(
                    "UPDATE transaction_projections SET is_duplicate=1, primary_transaction_id=? "
                    "WHERE transaction_id=?",
                    ("aaaa000000000001", "bbbb000000000002"),
                )
                conn.commit()
            finally:
                conn.close()

            rc = run(workspace=workspace)
            assert rc == 1

    def it_should_return_one_when_stale_primary_present(self):
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workspace, projection_builder, event_store = _build_minimal_workspace(tmp_path)

            _import_txn(event_store, "aaaa000000000001")
            projection_builder.build_from_scratch(event_store)

            # Corrupt: aaaa points at a nonexistent primary
            conn = sqlite3.connect(projection_builder.db_path)
            try:
                conn.execute(
                    "UPDATE transaction_projections SET is_duplicate=1, primary_transaction_id=? "
                    "WHERE transaction_id=?",
                    ("nonexistent000000", "aaaa000000000001"),
                )
                conn.commit()
            finally:
                conn.close()

            rc = run(workspace=workspace)
            assert rc == 1

    def it_should_return_one_when_self_referential_primary_present(self):
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workspace, projection_builder, event_store = _build_minimal_workspace(tmp_path)

            _import_txn(event_store, "aaaa000000000001")
            projection_builder.build_from_scratch(event_store)

            # Corrupt: aaaa points at itself
            conn = sqlite3.connect(projection_builder.db_path)
            try:
                conn.execute(
                    "UPDATE transaction_projections SET is_duplicate=1, primary_transaction_id=? "
                    "WHERE transaction_id=?",
                    ("aaaa000000000001", "aaaa000000000001"),
                )
                conn.commit()
            finally:
                conn.close()

            rc = run(workspace=workspace)
            assert rc == 1

    def it_should_return_one_when_projections_db_is_missing(self):
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workspace = Workspace(root=tmp_path)
            # No projections.db created
            rc = run(workspace=workspace)
            assert rc == 1
