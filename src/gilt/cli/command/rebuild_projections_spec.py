from __future__ import annotations

"""
Specs for the rebuild-projections CLI command.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

from pathlib import Path

from gilt.cli.command.rebuild_projections import run
from gilt.conftest import make_workspace
from gilt.model.events import TransactionImported
from gilt.storage.event_store import EventStore


def _populate_event_store(event_store_path: Path) -> None:
    """Write a minimal TransactionImported event so the store is non-empty."""
    store = EventStore(str(event_store_path))
    store.append_event(
        TransactionImported(
            transaction_id="aaaa1111aaaa1111",
            transaction_date="2025-01-10",
            source_file="mybank_export.csv",
            source_account="MYBANK_CHQ",
            raw_description="EXAMPLE UTILITY",
            amount="-100.00",
            currency="CAD",
            raw_data={"description": "EXAMPLE UTILITY", "amount": "-100.00"},
        )
    )


class DescribeRebuildProjections:
    def it_should_return_one_when_event_store_missing(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])

        result = run(workspace=ws)

        assert result == 1

    def it_should_return_zero_on_success(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        _populate_event_store(ws.event_store_path)

        result = run(workspace=ws)

        assert result == 0

    def it_should_create_projections_database(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        _populate_event_store(ws.event_store_path)

        run(workspace=ws)

        assert ws.projections_path.exists()

    def it_should_return_zero_for_empty_event_store(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        # Create an event store file but put no events in it
        EventStore(str(ws.event_store_path))

        result = run(workspace=ws)

        assert result == 0

    def it_should_rebuild_from_scratch_when_flag_set(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        _populate_event_store(ws.event_store_path)

        result = run(workspace=ws, from_scratch=True)

        assert result == 0
        assert ws.projections_path.exists()
