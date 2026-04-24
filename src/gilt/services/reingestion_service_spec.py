"""
Tests for ReingestionService.

These tests verify the functional core of the reingest purge workflow:
- Collecting transaction IDs for an account
- Collecting event IDs that reference an account's transactions
- Purging via proper storage APIs (not raw SQL)
- Purging intelligence cache entries
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from gilt.model.events import TransactionCategorized, TransactionImported
from gilt.services.reingestion_service import (
    ReingestionService,
    purge_cache_entries,
)
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder


def _make_import_event(txn_id: str, account_id: str) -> TransactionImported:
    return TransactionImported(
        transaction_date="2025-01-10",
        transaction_id=txn_id,
        source_file="test.csv",
        source_account=account_id,
        raw_description="EXAMPLE UTILITY",
        amount=Decimal("-50.00"),
        currency="CAD",
        raw_data={},
    )


class DescribeReingestionService:
    """Base fixtures for reingest service tests."""

    @pytest.fixture
    def temp_dir(self, tmp_path: Path) -> Path:
        return tmp_path

    @pytest.fixture
    def event_store(self, temp_dir: Path) -> EventStore:
        return EventStore(str(temp_dir / "events.db"))

    @pytest.fixture
    def projection_builder(self, temp_dir: Path) -> ProjectionBuilder:
        return ProjectionBuilder(temp_dir / "projections.db")

    @pytest.fixture
    def service(self, event_store, projection_builder, temp_dir):
        return ReingestionService(
            event_store=event_store,
            projection_builder=projection_builder,
            ledger_data_dir=temp_dir / "accounts",
            intelligence_cache_path=temp_dir / "intelligence_cache.json",
        )


class DescribePlanPurge(DescribeReingestionService):
    """Tests for plan_purge method."""

    def it_should_collect_transaction_ids_for_account(self, service, event_store):
        """Should find all transaction IDs imported for the given account."""
        event_store.append_event(_make_import_event("txn001", "MYBANK_CHQ"))
        event_store.append_event(_make_import_event("txn002", "MYBANK_CHQ"))
        event_store.append_event(_make_import_event("txn003", "MYBANK_CC"))

        plan = service.plan_purge("MYBANK_CHQ")

        assert "txn001" in plan.transaction_ids
        assert "txn002" in plan.transaction_ids
        assert "txn003" not in plan.transaction_ids

    def it_should_collect_event_ids_referencing_account_transactions(self, service, event_store):
        """Should include events that reference the account's transactions."""
        import_evt = _make_import_event("txn001", "MYBANK_CHQ")
        event_store.append_event(import_evt)

        cat_evt = TransactionCategorized(
            transaction_id="txn001",
            category="Utilities",
            subcategory=None,
            source="user",
            confidence=1.0,
        )
        event_store.append_event(cat_evt)

        plan = service.plan_purge("MYBANK_CHQ")

        assert import_evt.event_id in plan.event_ids
        assert cat_evt.event_id in plan.event_ids

    def it_should_not_include_events_for_other_accounts(self, service, event_store):
        """Should only include events for the target account."""
        event_store.append_event(_make_import_event("txn001", "MYBANK_CHQ"))
        other_evt = _make_import_event("txn002", "MYBANK_CC")
        event_store.append_event(other_evt)

        plan = service.plan_purge("MYBANK_CHQ")

        assert other_evt.event_id not in plan.event_ids

    def it_should_return_empty_plan_for_unknown_account(self, service, event_store):
        """Should return a plan with no transactions for an account not in store."""
        plan = service.plan_purge("UNKNOWN_ACCT")

        assert len(plan.transaction_ids) == 0
        assert len(plan.event_ids) == 0


class DescribeExecutePurge(DescribeReingestionService):
    """Tests for execute_purge method."""

    def it_should_purge_events_via_event_store_api(self, service, event_store):
        """Should delete events using EventStore.delete_events."""
        event_store.append_event(_make_import_event("txn001", "MYBANK_CHQ"))
        plan = service.plan_purge("MYBANK_CHQ")

        result = service.execute_purge(plan)

        assert result.events_purged == len(plan.event_ids)
        assert event_store.get_events_by_type("TransactionImported") == []

    def it_should_purge_projections_via_projection_builder_api(
        self, service, event_store, projection_builder
    ):
        """Should delete projection rows and reset metadata using ProjectionBuilder."""
        event_store.append_event(_make_import_event("txn001", "MYBANK_CHQ"))
        projection_builder.rebuild_from_scratch(event_store)
        assert len(projection_builder.get_all_transactions()) == 1

        plan = service.plan_purge("MYBANK_CHQ")
        service.execute_purge(plan)

        assert len(projection_builder.get_all_transactions()) == 0

    def it_should_purge_intelligence_cache_entries(self, service, temp_dir, event_store):
        """Should remove cached intelligence entries for the account's transactions."""
        cache_path = temp_dir / "intelligence_cache.json"
        cache_data = {"txn001": {"result": "x"}, "txn999": {"result": "y"}}
        cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

        event_store.append_event(_make_import_event("txn001", "MYBANK_CHQ"))
        plan = service.plan_purge("MYBANK_CHQ")
        result = service.execute_purge(plan)

        assert result.cache_entries_purged == 1
        remaining = json.loads(cache_path.read_text(encoding="utf-8"))
        assert "txn001" not in remaining
        assert "txn999" in remaining

    def it_should_return_zero_cache_purged_when_no_cache_file(self, service, event_store):
        """Should return 0 cache entries purged when cache file does not exist."""
        event_store.append_event(_make_import_event("txn001", "MYBANK_CHQ"))
        plan = service.plan_purge("MYBANK_CHQ")
        result = service.execute_purge(plan)

        assert result.cache_entries_purged == 0


class DescribePurgeCacheEntries:
    def it_should_remove_entries_matching_txn_ids(self):
        data = {"txn001": {"result": "x"}, "txn002": {"result": "y"}, "txn003": {"result": "z"}}

        filtered, count = purge_cache_entries(data, {"txn001", "txn002"})

        assert count == 2
        assert "txn001" not in filtered
        assert "txn002" not in filtered
        assert "txn003" in filtered

    def it_should_return_zero_when_no_ids_match(self):
        data = {"txn999": {"result": "x"}}

        filtered, count = purge_cache_entries(data, {"txn001"})

        assert count == 0
        assert filtered == data

    def it_should_handle_empty_data(self):
        filtered, count = purge_cache_entries({}, {"txn001"})

        assert count == 0
        assert filtered == {}
