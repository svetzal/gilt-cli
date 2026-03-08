from __future__ import annotations

from pathlib import Path

from gilt.cli.command.reingest import (
    _collect_event_ids_to_purge,
    _collect_transaction_ids_for_account,
)
from gilt.model.events import (
    TransactionCategorized,
    TransactionImported,
)
from gilt.storage.event_store import EventStore


def _make_event_store(tmp_path: Path) -> EventStore:
    return EventStore(str(tmp_path / "events.db"))


def _import_event(account: str, txn_id: str = "txn_0001") -> TransactionImported:
    return TransactionImported(
        transaction_id=txn_id,
        source_file="test.csv",
        source_account=account,
        raw_description="SAMPLE STORE",
        amount=42.50,
        currency="CAD",
        transaction_date="2025-01-15",
        raw_data={},
    )


def _categorize_event(txn_id: str) -> TransactionCategorized:
    return TransactionCategorized(
        transaction_id=txn_id,
        category="Food",
        subcategory="Groceries",
        source="user",
    )


class DescribeCollectTransactionIdsForAccount:
    def it_should_find_transaction_ids_for_target_account(self, tmp_path):
        store = _make_event_store(tmp_path)
        store.append_event(_import_event("MYBANK_CHQ", "txn_0001"))
        store.append_event(_import_event("MYBANK_CC", "txn_0002"))
        store.append_event(_import_event("MYBANK_CHQ", "txn_0003"))

        ids = _collect_transaction_ids_for_account(store, "MYBANK_CHQ")
        assert ids == {"txn_0001", "txn_0003"}

    def it_should_return_empty_set_for_unknown_account(self, tmp_path):
        store = _make_event_store(tmp_path)
        store.append_event(_import_event("MYBANK_CHQ", "txn_0001"))

        ids = _collect_transaction_ids_for_account(store, "UNKNOWN")
        assert ids == set()


class DescribeCollectEventIdsToPurge:
    def it_should_collect_import_events_for_account(self, tmp_path):
        store = _make_event_store(tmp_path)
        evt = _import_event("MYBANK_CHQ", "txn_0001")
        store.append_event(evt)

        txn_ids = {"txn_0001"}
        event_ids = _collect_event_ids_to_purge(store, "MYBANK_CHQ", txn_ids)
        assert evt.event_id in event_ids

    def it_should_collect_derived_events_referencing_account_transactions(self, tmp_path):
        store = _make_event_store(tmp_path)
        imp = _import_event("MYBANK_CHQ", "txn_0001")
        store.append_event(imp)
        cat = _categorize_event("txn_0001")
        store.append_event(cat)

        txn_ids = {"txn_0001"}
        event_ids = _collect_event_ids_to_purge(store, "MYBANK_CHQ", txn_ids)
        assert imp.event_id in event_ids
        assert cat.event_id in event_ids

    def it_should_not_collect_events_for_other_accounts(self, tmp_path):
        store = _make_event_store(tmp_path)
        other_imp = _import_event("MYBANK_CC", "txn_0002")
        store.append_event(other_imp)
        other_cat = _categorize_event("txn_0002")
        store.append_event(other_cat)

        txn_ids: set[str] = set()
        event_ids = _collect_event_ids_to_purge(store, "MYBANK_CHQ", txn_ids)
        assert other_imp.event_id not in event_ids
        assert other_cat.event_id not in event_ids
