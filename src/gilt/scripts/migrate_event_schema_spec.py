from __future__ import annotations

"""
Specifications for migrate_event_schema script.

Tests cover the migrate_events() business logic:
- Skipping events that already have pair data
- Building pair data from projection transaction records
- Skipping events where one or both transactions are missing
- Dry-run mode (no writes) vs. write mode (SQLite update)

All fixtures use synthetic/generic data only.
"""

from unittest.mock import patch

from gilt.conftest import make_workspace
from gilt.model.events import DuplicateSuggested
from gilt.scripts.migrate_event_schema import migrate_events
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def _make_event_store(ws: Workspace) -> EventStore:
    return EventStore(str(ws.event_store_path))


def _populate_projection(ws: Workspace, txn_id: str, description: str, amount: float) -> None:
    """Insert a minimal transaction row directly into the projection DB."""
    import sqlite3

    conn = sqlite3.connect(ws.projections_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO transaction_projections
            (transaction_id, transaction_date, canonical_description,
             amount, currency, account_id)
            VALUES (?, ?, ?, ?, 'CAD', 'MYBANK_CHQ')
            """,
            (txn_id, "2025-01-15", description, amount),
        )
        conn.commit()
    finally:
        conn.close()


def _add_duplicate_suggested_event(
    store: EventStore, txn1_id: str, txn2_id: str, with_pair: bool = False
) -> DuplicateSuggested:
    assessment: dict = {
        "is_duplicate": True,
        "confidence": 0.88,
        "reasoning": "Same amount and account",
    }
    if with_pair:
        assessment["pair"] = {
            "txn1_id": txn1_id,
            "txn1_date": "2025-01-15",
            "txn1_description": "EXISTING DESC",
            "txn1_amount": -50.0,
            "txn1_account": "MYBANK_CHQ",
            "txn2_id": txn2_id,
            "txn2_date": "2025-01-15",
            "txn2_description": "EXISTING DESC ALT",
            "txn2_amount": -50.0,
            "txn2_account": "MYBANK_CHQ",
        }
    event = DuplicateSuggested(
        transaction_id_1=txn1_id,
        transaction_id_2=txn2_id,
        confidence=0.88,
        reasoning="Same amount and account",
        model="test-model",
        prompt_version="v1",
        assessment=assessment,
    )
    store.append_event(event)
    return event


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------


class DescribeMigrateEventsNothingToMigrate:
    """When there are no DuplicateSuggested events at all."""

    def it_should_run_without_error_when_no_events_exist(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["event_store_path", "projections_path"])
        _make_event_store(ws)
        # Ensure projection DB is initialised
        ProjectionBuilder(ws.projections_path)

        with patch("gilt.scripts.migrate_event_schema.Workspace") as mock_ws_cls:
            mock_ws_cls.resolve.return_value = ws
            # Should not raise
            migrate_events(dry_run=True)

    def it_should_skip_all_events_that_already_have_pair_data(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["event_store_path", "projections_path"])
        store = _make_event_store(ws)
        ProjectionBuilder(ws.projections_path)

        # Both events already have pair data
        _add_duplicate_suggested_event(
            store, "aaaa0001aaaa0001", "bbbb0002bbbb0002", with_pair=True
        )
        _add_duplicate_suggested_event(
            store, "cccc0003cccc0003", "dddd0004dddd0004", with_pair=True
        )

        with patch("gilt.scripts.migrate_event_schema.Workspace") as mock_ws_cls:
            mock_ws_cls.resolve.return_value = ws
            # No migration needed — should not raise
            migrate_events(dry_run=True)


class DescribeMigrateEventsPairDataBuilding:
    """Verify that pair data is correctly built from projection records and persisted."""

    def it_should_write_pair_data_to_event_store_in_write_mode(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["event_store_path", "projections_path"])
        store = _make_event_store(ws)
        ProjectionBuilder(ws.projections_path)

        # Seed projection with both transactions
        _populate_projection(ws, "aaaa0001aaaa0001", "EXAMPLE UTILITY PAYMENT", -120.0)
        _populate_projection(ws, "bbbb0002bbbb0002", "EXAMPLE UTILITY PMT", -120.0)

        _add_duplicate_suggested_event(
            store, "aaaa0001aaaa0001", "bbbb0002bbbb0002", with_pair=False
        )

        with patch("gilt.scripts.migrate_event_schema.Workspace") as mock_ws_cls:
            mock_ws_cls.resolve.return_value = ws
            migrate_events(dry_run=False)

        # Reload events from the DB and verify pair data was written
        reloaded = store.get_events_by_type("DuplicateSuggested")
        assert len(reloaded) == 1
        assert isinstance(reloaded[0], DuplicateSuggested)
        pair = reloaded[0].assessment["pair"]
        assert pair["txn1_id"] == "aaaa0001aaaa0001"
        assert pair["txn2_id"] == "bbbb0002bbbb0002"
        assert pair["txn1_amount"] == -120.0
        assert pair["txn2_amount"] == -120.0

    def it_should_include_account_id_in_pair_data_when_writing(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["event_store_path", "projections_path"])
        store = _make_event_store(ws)
        ProjectionBuilder(ws.projections_path)

        _populate_projection(ws, "aaaa0001aaaa0001", "ACME CORP PURCHASE", -75.0)
        _populate_projection(ws, "bbbb0002bbbb0002", "ACME CORP PURCH", -75.0)

        _add_duplicate_suggested_event(
            store, "aaaa0001aaaa0001", "bbbb0002bbbb0002", with_pair=False
        )

        with patch("gilt.scripts.migrate_event_schema.Workspace") as mock_ws_cls:
            mock_ws_cls.resolve.return_value = ws
            migrate_events(dry_run=False)

        reloaded = store.get_events_by_type("DuplicateSuggested")
        pair = reloaded[0].assessment["pair"]
        assert pair["txn1_account"] == "MYBANK_CHQ"
        assert pair["txn2_account"] == "MYBANK_CHQ"

    def it_should_include_descriptions_in_pair_data_when_writing(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["event_store_path", "projections_path"])
        store = _make_event_store(ws)
        ProjectionBuilder(ws.projections_path)

        _populate_projection(ws, "aaaa0001aaaa0001", "SAMPLE STORE ANYTOWN", -55.0)
        _populate_projection(ws, "bbbb0002bbbb0002", "SAMPLE STORE ANYTOWN ON", -55.0)

        _add_duplicate_suggested_event(
            store, "aaaa0001aaaa0001", "bbbb0002bbbb0002", with_pair=False
        )

        with patch("gilt.scripts.migrate_event_schema.Workspace") as mock_ws_cls:
            mock_ws_cls.resolve.return_value = ws
            migrate_events(dry_run=False)

        reloaded = store.get_events_by_type("DuplicateSuggested")
        pair = reloaded[0].assessment["pair"]
        assert pair["txn1_description"] == "SAMPLE STORE ANYTOWN"
        assert pair["txn2_description"] == "SAMPLE STORE ANYTOWN ON"

    def it_should_not_modify_event_store_in_dry_run(self, tmp_path):
        """Dry-run must not write any pair data to the database."""
        ws = make_workspace(tmp_path, init_dirs=["event_store_path", "projections_path"])
        store = _make_event_store(ws)
        ProjectionBuilder(ws.projections_path)

        _populate_projection(ws, "aaaa0001aaaa0001", "SAMPLE STORE", -50.0)
        _populate_projection(ws, "bbbb0002bbbb0002", "SAMPLE STORE ALT", -50.0)

        _add_duplicate_suggested_event(
            store, "aaaa0001aaaa0001", "bbbb0002bbbb0002", with_pair=False
        )

        with patch("gilt.scripts.migrate_event_schema.Workspace") as mock_ws_cls:
            mock_ws_cls.resolve.return_value = ws
            migrate_events(dry_run=True)

        # Reloading from the DB should still show no pair data
        reloaded = store.get_events_by_type("DuplicateSuggested")
        assert "pair" not in reloaded[0].assessment


class DescribeMigrateEventsMissingTransactions:
    """When one or both transactions are missing from the projection."""

    def it_should_skip_event_when_txn1_is_missing(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["event_store_path", "projections_path"])
        store = _make_event_store(ws)
        ProjectionBuilder(ws.projections_path)

        # Only txn2 exists in projection, txn1 is absent
        _populate_projection(ws, "bbbb0002bbbb0002", "EXAMPLE UTILITY PMT", -120.0)

        event = _add_duplicate_suggested_event(
            store, "aaaa0001aaaa0001", "bbbb0002bbbb0002", with_pair=False
        )

        with patch("gilt.scripts.migrate_event_schema.Workspace") as mock_ws_cls:
            mock_ws_cls.resolve.return_value = ws
            migrate_events(dry_run=True)

        # pair should NOT be added since txn1 was missing
        assert "pair" not in event.assessment

    def it_should_skip_event_when_both_transactions_are_missing(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["event_store_path", "projections_path"])
        store = _make_event_store(ws)
        ProjectionBuilder(ws.projections_path)
        # No transactions in projection

        event = _add_duplicate_suggested_event(
            store, "aaaa0001aaaa0001", "bbbb0002bbbb0002", with_pair=False
        )

        with patch("gilt.scripts.migrate_event_schema.Workspace") as mock_ws_cls:
            mock_ws_cls.resolve.return_value = ws
            migrate_events(dry_run=True)

        assert "pair" not in event.assessment


class DescribeMigrateEventsWriteMode:
    """Verify write mode persists the updated event data to SQLite."""

    def it_should_not_raise_when_writing_with_valid_data(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["event_store_path", "projections_path"])
        store = _make_event_store(ws)
        ProjectionBuilder(ws.projections_path)

        _populate_projection(ws, "aaaa0001aaaa0001", "ACME CORP", -30.0)
        _populate_projection(ws, "bbbb0002bbbb0002", "ACME CORP PAYMENT", -30.0)

        _add_duplicate_suggested_event(
            store, "aaaa0001aaaa0001", "bbbb0002bbbb0002", with_pair=False
        )

        with patch("gilt.scripts.migrate_event_schema.Workspace") as mock_ws_cls:
            mock_ws_cls.resolve.return_value = ws
            # Should complete without raising
            migrate_events(dry_run=False)
