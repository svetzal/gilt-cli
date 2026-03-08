from __future__ import annotations

"""
Tests for TransactionService projection-based loading.

Verifies that load_all_transactions reads from the projections database,
respects the is_duplicate flag, and correctly converts projection rows
to TransactionGroup objects.
"""

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from gilt.gui.services.transaction_service import TransactionService
from gilt.model.events import (
    DuplicateConfirmed,
    TransactionCategorized,
    TransactionImported,
)
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder


def _import_transaction(
    event_store: EventStore,
    transaction_id: str,
    account: str = "MYBANK_CHQ",
    description: str = "SAMPLE STORE",
    amount: Decimal = Decimal("-25.00"),
    date: str = "2025-06-15",
    currency: str = "CAD",
):
    """Helper: append a TransactionImported event."""
    event = TransactionImported(
        transaction_date=date,
        transaction_id=transaction_id,
        source_file="test.csv",
        source_account=account,
        raw_description=description,
        amount=amount,
        currency=currency,
        raw_data={"description": description},
    )
    event_store.append_event(event)


class DescribeTransactionServiceProjectionLoading:
    """Tests for loading transactions from the projections database."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def data_dir(self, temp_dir):
        accounts_dir = temp_dir / "accounts"
        accounts_dir.mkdir()
        return accounts_dir

    @pytest.fixture
    def event_store(self, temp_dir):
        return EventStore(str(temp_dir / "events.db"))

    @pytest.fixture
    def projection_builder(self, temp_dir):
        return ProjectionBuilder(temp_dir / "projections.db")

    @pytest.fixture
    def service(self, data_dir, temp_dir):
        return TransactionService(
            data_dir, projections_db_path=temp_dir / "projections.db"
        )

    def it_should_load_transactions_from_projections(
        self, event_store, projection_builder, service
    ):
        _import_transaction(event_store, "txn001", description="ACME CORP")
        _import_transaction(event_store, "txn002", description="SAMPLE STORE")
        projection_builder.rebuild_from_scratch(event_store)

        groups = service.load_all_transactions()

        assert len(groups) == 2
        ids = {g.primary.transaction_id for g in groups}
        assert ids == {"txn001", "txn002"}

    def it_should_exclude_duplicates_by_default(
        self, event_store, projection_builder, service
    ):
        _import_transaction(event_store, "txn001", description="ACME CORP")
        _import_transaction(event_store, "txn002", description="ACME CORP UPDATED")
        event_store.append_event(
            DuplicateConfirmed(
                primary_transaction_id="txn001",
                duplicate_transaction_id="txn002",
                canonical_description="ACME CORP",
                suggestion_event_id="sug001",
                llm_was_correct=True,
            )
        )
        projection_builder.rebuild_from_scratch(event_store)

        groups = service.load_all_transactions()

        assert len(groups) == 1
        assert groups[0].primary.transaction_id == "txn001"

    def it_should_include_duplicates_when_requested(
        self, event_store, projection_builder, service
    ):
        _import_transaction(event_store, "txn001", description="ACME CORP")
        _import_transaction(event_store, "txn002", description="ACME CORP UPDATED")
        event_store.append_event(
            DuplicateConfirmed(
                primary_transaction_id="txn001",
                duplicate_transaction_id="txn002",
                canonical_description="ACME CORP",
                suggestion_event_id="sug001",
                llm_was_correct=True,
            )
        )
        projection_builder.rebuild_from_scratch(event_store)

        groups = service.load_all_transactions(include_duplicates=True)

        assert len(groups) == 2

    def it_should_map_projection_fields_correctly(
        self, event_store, projection_builder, service
    ):
        _import_transaction(
            event_store,
            "txn001",
            account="MYBANK_CHQ",
            description="EXAMPLE UTILITY",
            amount=Decimal("-99.50"),
            date="2025-03-10",
            currency="CAD",
        )
        event_store.append_event(
            TransactionCategorized(
                transaction_id="txn001",
                category="Utilities",
                subcategory="Electric",
                source="user",
            )
        )
        projection_builder.rebuild_from_scratch(event_store)

        groups = service.load_all_transactions()

        assert len(groups) == 1
        txn = groups[0].primary
        assert txn.transaction_id == "txn001"
        assert str(txn.date) == "2025-03-10"
        assert txn.description == "EXAMPLE UTILITY"
        assert txn.amount == -99.50
        assert txn.currency == "CAD"
        assert txn.account_id == "MYBANK_CHQ"
        assert txn.category == "Utilities"
        assert txn.subcategory == "Electric"
        assert groups[0].group_id == "txn001"

    def it_should_fall_back_to_csv_when_no_projections_db(self, data_dir):
        service = TransactionService(
            data_dir, projections_db_path=data_dir.parent / "nonexistent.db"
        )
        # Write a minimal CSV
        csv_content = (
            "row_type,group_id,transaction_id,date,description,amount,"
            "currency,account_id,counterparty,category,subcategory,"
            "notes,source_file,metadata_json,line_id,target_account_id,"
            "split_category,split_subcategory,split_memo,split_percent\n"
            "primary,txn_csv,txn_csv,2025-01-01,CSV TXN,-10.00,CAD,"
            "MYBANK_CHQ,,,,,test.csv,,,,,,,"
        )
        (data_dir / "MYBANK_CHQ.csv").write_text(csv_content, encoding="utf-8")

        groups = service.load_all_transactions()

        assert len(groups) == 1
        assert groups[0].primary.transaction_id == "txn_csv"

    def it_should_get_available_accounts_from_projections(
        self, event_store, projection_builder, service
    ):
        _import_transaction(event_store, "txn001", account="MYBANK_CHQ")
        _import_transaction(event_store, "txn002", account="MYBANK_CC")
        _import_transaction(event_store, "txn003", account="BANK2_BIZ")
        projection_builder.rebuild_from_scratch(event_store)

        accounts = service.get_available_accounts()

        assert accounts == ["BANK2_BIZ", "MYBANK_CC", "MYBANK_CHQ"]

    def it_should_filter_transactions_with_projection_sourced_data(
        self, event_store, projection_builder, service
    ):
        _import_transaction(
            event_store, "txn001", account="MYBANK_CHQ", description="ACME CORP"
        )
        _import_transaction(
            event_store, "txn002", account="MYBANK_CC", description="SAMPLE STORE"
        )
        projection_builder.rebuild_from_scratch(event_store)

        groups = service.load_all_transactions()
        filtered = service.filter_transactions(
            groups, account_filter=["MYBANK_CHQ"]
        )

        assert len(filtered) == 1
        assert filtered[0].primary.account_id == "MYBANK_CHQ"

    def it_should_filter_by_search_text_with_projection_data(
        self, event_store, projection_builder, service
    ):
        _import_transaction(
            event_store, "txn001", description="ACME CORP PAYMENT"
        )
        _import_transaction(
            event_store, "txn002", description="SAMPLE STORE PURCHASE"
        )
        projection_builder.rebuild_from_scratch(event_store)

        groups = service.load_all_transactions()
        filtered = service.filter_transactions(groups, search_text="acme")

        assert len(filtered) == 1
        assert filtered[0].primary.description == "ACME CORP PAYMENT"
