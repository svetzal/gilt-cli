from __future__ import annotations

"""
Specs for the duplicates CLI command.

Focuses on _setup_event_sourcing guard logic and basic run() scenarios.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from rich.console import Console

from gilt.cli.command.duplicates import run
from gilt.cli.command.util import require_event_sourcing
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.events import TransactionImported
from gilt.model.ledger_io import dump_ledger_csv
from gilt.services.event_sourcing_service import EventSourcingReadyResult
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quiet_console() -> Console:  # noqa: F401 (kept for potential future use)
    """Create a Rich console that discards all output (for test isolation)."""
    return Console(quiet=True)


def _write_synthetic_ledger(data_dir: Path, account_id: str = "MYBANK_CHQ") -> None:
    """Write a minimal synthetic ledger CSV."""
    groups = [
        TransactionGroup(
            group_id="grp001",
            primary=Transaction(
                transaction_id="aaaa0001aaaa0001",
                date="2025-01-10",
                description="SAMPLE STORE",
                amount=-50.0,
                currency="CAD",
                account_id=account_id,
            ),
        ),
    ]
    (data_dir / f"{account_id}.csv").write_text(dump_ledger_csv(groups), encoding="utf-8")


def _build_event_store_and_projections(ws: Workspace) -> None:
    """Populate an event store and build projections from synthetic data."""
    ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
    store = EventStore(str(ws.event_store_path))
    store.append_event(
        TransactionImported(
            transaction_id="aaaa0001aaaa0001",
            transaction_date="2025-01-10",
            source_file="mybank_export.csv",
            source_account="MYBANK_CHQ",
            raw_description="SAMPLE STORE",
            amount=Decimal("-50.00"),
            currency="CAD",
            raw_data={},
        )
    )
    builder = ProjectionBuilder(ws.projections_path)
    builder.rebuild_from_scratch(store)


# ---------------------------------------------------------------------------
# _setup_event_sourcing guard logic
# ---------------------------------------------------------------------------


class DescribeSetupEventSourcing:
    """Specs for require_event_sourcing guard checks (formerly _setup_event_sourcing)."""

    def it_should_return_none_when_data_dir_does_not_exist(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            # data dir intentionally NOT created
            result = require_event_sourcing(ws)
            assert result is None

    def it_should_return_none_when_data_dir_exists_but_no_event_store_and_csvs_present(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            # Put CSV file(s) but no event store
            _write_synthetic_ledger(ws.ledger_data_dir)
            # No event store created

            result = require_event_sourcing(ws)
            assert result is None

    def it_should_return_none_when_data_dir_exists_but_no_event_store_and_no_csvs(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            # No CSVs, no event store

            result = require_event_sourcing(ws)
            assert result is None

    def it_should_return_ready_result_when_event_store_and_projections_exist(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)
            _build_event_store_and_projections(ws)

            result = require_event_sourcing(ws)
            assert isinstance(result, EventSourcingReadyResult)
            assert result.ready is True
            assert result.event_store is not None
            assert result.projection_builder is not None

    def it_should_rebuild_projections_when_they_do_not_yet_exist(self):
        """When the event store exists but projections are missing,
        require_event_sourcing should rebuild them and return a ready result."""
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)

            # Create event store but NOT projections
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            store = EventStore(str(ws.event_store_path))
            store.append_event(
                TransactionImported(
                    transaction_id="bbbb0001bbbb0001",
                    transaction_date="2025-02-01",
                    source_file="mybank_export.csv",
                    source_account="MYBANK_CHQ",
                    raw_description="ACME CORP",
                    amount=Decimal("-75.00"),
                    currency="CAD",
                    raw_data={},
                )
            )
            # Projections deliberately NOT built

            result = require_event_sourcing(ws)
            assert isinstance(result, EventSourcingReadyResult)
            assert result.ready is True
            # Projections should now exist
            assert ws.projections_path.exists()


# ---------------------------------------------------------------------------
# run() — high-level scenarios
# ---------------------------------------------------------------------------


class DescribeDuplicatesRun:
    """Specs for the duplicates run() function."""

    def it_should_return_1_when_data_dir_does_not_exist(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            # Data dir intentionally absent

            result = run(workspace=ws)
            assert result == 1

    def it_should_return_0_when_no_candidate_pairs_found(self):
        """With a single unique transaction there are no duplicates to detect."""
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)
            _build_event_store_and_projections(ws)

            result = run(workspace=ws)
            assert result == 0
