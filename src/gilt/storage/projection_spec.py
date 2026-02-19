"""
Tests for transaction projection builder.

These tests verify that projections can be correctly built from events
and that the rebuild process is idempotent and accurate.
"""

from decimal import Decimal
from pathlib import Path
import tempfile

import pytest

from gilt.model.events import (
    TransactionImported,
    TransactionDescriptionObserved,
    TransactionCategorized,
    TransactionEnriched,
)
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder


class DescribeProjectionBuilder:
    """Tests for ProjectionBuilder class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test databases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def event_store(self, temp_dir):
        """Create event store for testing."""
        db_path = temp_dir / "events.db"
        return EventStore(str(db_path))

    @pytest.fixture
    def projection_builder(self, temp_dir):
        """Create projection builder for testing."""
        db_path = temp_dir / "projections.db"
        return ProjectionBuilder(db_path)

    def it_should_create_projection_schema(self, temp_dir):
        """Test that projection schema is created on initialization."""
        db_path = temp_dir / "projections.db"
        builder = ProjectionBuilder(db_path)

        # Verify database file was created
        assert db_path.exists()

        # Verify we can query the schema
        txn = builder.get_transaction("nonexistent")
        assert txn is None

    def it_should_build_projection_from_imported_event(self, event_store, projection_builder):
        """Test building projection from TransactionImported event."""
        # Create and store event
        event = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="Test Transaction",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={"date": "10/15/2025", "description": "Test Transaction"},
        )
        event_store.append_event(event)

        # Build projection
        processed = projection_builder.rebuild_from_scratch(event_store)
        assert processed == 1

        # Verify projection
        txn = projection_builder.get_transaction("abc123")
        assert txn is not None
        assert txn["transaction_id"] == "abc123"
        assert txn["transaction_date"] == "2025-10-15"
        assert txn["canonical_description"] == "Test Transaction"
        assert txn["amount"] == -10.31
        assert txn["currency"] == "CAD"
        assert txn["account_id"] == "TEST_ACCT"
        assert txn["source_file"] == "test.csv"

        # Verify description history
        import json

        history = json.loads(txn["description_history"])
        assert history == ["Test Transaction"]

    def it_should_be_idempotent_on_reimport(self, event_store, projection_builder):
        """Test that re-importing same event doesn't duplicate projection."""
        # Create two events with same transaction_id but different event_id
        # (simulating re-import of same CSV data)
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="Test Transaction",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={},
        )
        event2 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",  # Same transaction_id
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="Test Transaction",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={},
        )

        # Import twice with different event instances
        event_store.append_event(event1)
        event_store.append_event(event2)

        # Build projection
        projection_builder.rebuild_from_scratch(event_store)

        # Should only have one transaction (idempotent on transaction_id)
        transactions = projection_builder.get_all_transactions()
        assert len(transactions) == 1

    def it_should_track_description_evolution(self, event_store, projection_builder):
        """Test that TransactionDescriptionObserved updates projection correctly."""
        # Import original transaction
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test1.csv",
            source_account="TEST_ACCT",
            raw_description="TRANSIT FARE/REF1234ABCD Exampleville",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event1)

        # Observe description change
        event2 = TransactionDescriptionObserved(
            original_transaction_id="abc123",
            new_transaction_id="xyz789",  # Different ID due to description
            transaction_date="2025-10-15",
            original_description="TRANSIT FARE/REF1234ABCD Exampleville",
            new_description="TRANSIT FARE/REF1234ABCD Exampleville ON",
            source_file="test2.csv",
            source_account="TEST_ACCT",
            amount=Decimal("-10.31"),
        )
        event_store.append_event(event2)

        # Build projection
        projection_builder.rebuild_from_scratch(event_store)

        # Verify original transaction was updated
        txn = projection_builder.get_transaction("abc123")
        assert txn is not None
        assert txn["canonical_description"] == "TRANSIT FARE/REF1234ABCD Exampleville ON"

        # Verify description history includes both
        import json

        history = json.loads(txn["description_history"])
        assert len(history) == 2
        assert "TRANSIT FARE/REF1234ABCD Exampleville" in history
        assert "TRANSIT FARE/REF1234ABCD Exampleville ON" in history

    def it_should_mark_new_txn_as_duplicate_after_description_observed(
        self, event_store, projection_builder
    ):
        """Test that new transaction_id is marked as duplicate when description evolves."""
        # Import both transactions separately first
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test1.csv",
            source_account="TEST_ACCT",
            raw_description="TRANSIT FARE Exampleville",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={},
        )
        event2 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="xyz789",
            source_file="test2.csv",
            source_account="TEST_ACCT",
            raw_description="TRANSIT FARE Exampleville ON",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event1)
        event_store.append_event(event2)

        # Then observe they're the same
        event3 = TransactionDescriptionObserved(
            original_transaction_id="abc123",
            new_transaction_id="xyz789",
            transaction_date="2025-10-15",
            original_description="TRANSIT FARE Exampleville",
            new_description="TRANSIT FARE Exampleville ON",
            source_file="test2.csv",
            source_account="TEST_ACCT",
            amount=Decimal("-10.31"),
        )
        event_store.append_event(event3)

        # Build projection
        projection_builder.rebuild_from_scratch(event_store)

        # Verify xyz789 is marked as duplicate
        txn = projection_builder.get_transaction("xyz789")
        assert txn is not None
        assert txn["is_duplicate"] == 1
        assert txn["primary_transaction_id"] == "abc123"

        # Verify only one transaction returned by default
        transactions = projection_builder.get_all_transactions(include_duplicates=False)
        assert len(transactions) == 1
        assert transactions[0]["transaction_id"] == "abc123"

    def it_should_apply_categorization_events(self, event_store, projection_builder):
        """Test that TransactionCategorized events update projections."""
        # Import transaction
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="PRESTO FARE",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event1)

        # Categorize it
        event2 = TransactionCategorized(
            transaction_id="abc123",
            category="Transportation",
            subcategory="Public Transit",
            source="user",
            confidence=1.0,
            previous_category=None,
            rationale="PRESTO card transactions",
        )
        event_store.append_event(event2)

        # Build projection
        projection_builder.rebuild_from_scratch(event_store)

        # Verify categorization
        txn = projection_builder.get_transaction("abc123")
        assert txn is not None
        assert txn["category"] == "Transportation"
        assert txn["subcategory"] == "Public Transit"

    def it_should_rebuild_incrementally(self, event_store, projection_builder):
        """Test incremental rebuild only processes new events."""
        # Import first transaction
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="Transaction 1",
            amount=Decimal("-10.00"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event1)

        # Initial rebuild
        processed = projection_builder.rebuild_from_scratch(event_store)
        assert processed == 1

        # Add second transaction
        event2 = TransactionImported(
            transaction_date="2025-10-16",
            transaction_id="xyz789",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="Transaction 2",
            amount=Decimal("-20.00"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event2)

        # Incremental rebuild
        processed = projection_builder.rebuild_incremental(event_store)
        assert processed == 1

        # Verify both transactions exist
        transactions = projection_builder.get_all_transactions()
        assert len(transactions) == 2

    def it_should_return_zero_when_already_up_to_date(self, event_store, projection_builder):
        """Test that incremental rebuild returns 0 when no new events."""
        # Import transaction
        event = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="Test",
            amount=Decimal("-10.00"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event)

        # Initial rebuild
        projection_builder.rebuild_from_scratch(event_store)

        # Try incremental rebuild with no new events
        processed = projection_builder.rebuild_incremental(event_store)
        assert processed == 0

    def it_should_handle_multiple_description_changes(self, event_store, projection_builder):
        """Test tracking multiple description changes for same transaction."""
        # Import original
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test1.csv",
            source_account="TEST_ACCT",
            raw_description="PRESTO",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event1)

        # First description change
        event2 = TransactionDescriptionObserved(
            original_transaction_id="abc123",
            new_transaction_id="def456",
            transaction_date="2025-10-15",
            original_description="PRESTO",
            new_description="TRANSIT Exampleville",
            source_file="test2.csv",
            source_account="TEST_ACCT",
            amount=Decimal("-10.31"),
        )
        event_store.append_event(event2)

        # Second description change
        event3 = TransactionDescriptionObserved(
            original_transaction_id="abc123",
            new_transaction_id="ghi789",
            transaction_date="2025-10-15",
            original_description="TRANSIT Exampleville",
            new_description="TRANSIT Exampleville ON",
            source_file="test3.csv",
            source_account="TEST_ACCT",
            amount=Decimal("-10.31"),
        )
        event_store.append_event(event3)

        # Build projection
        projection_builder.rebuild_from_scratch(event_store)

        # Verify all descriptions tracked
        txn = projection_builder.get_transaction("abc123")
        assert txn["canonical_description"] == "TRANSIT Exampleville ON"

        import json

        history = json.loads(txn["description_history"])
        assert len(history) == 3
        assert "PRESTO" in history
        assert "TRANSIT Exampleville" in history
        assert "TRANSIT Exampleville ON" in history

    def it_should_handle_duplicate_confirmed_event(self, event_store, projection_builder):
        """Test that DuplicateConfirmed marks duplicate and sets canonical description."""
        from gilt.model.events import DuplicateConfirmed

        # Import two transactions (potential duplicates)
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test1.csv",
            source_account="TEST_ACCT",
            raw_description="TRANSIT FARE Exampleville",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event1)

        event2 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="def456",
            source_file="test2.csv",
            source_account="TEST_ACCT",
            raw_description="TRANSIT FARE Exampleville ON",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event2)

        # User confirms as duplicate and chooses description
        event3 = DuplicateConfirmed(
            suggestion_event_id="suggestion-123",
            primary_transaction_id="abc123",
            duplicate_transaction_id="def456",
            canonical_description="TRANSIT FARE Exampleville ON",
            user_rationale="Prefer province suffix",
            llm_was_correct=True,
        )
        event_store.append_event(event3)

        # Build projection
        projection_builder.rebuild_from_scratch(event_store)

        # Verify primary transaction updated
        primary = projection_builder.get_transaction("abc123")
        assert primary is not None
        assert primary["canonical_description"] == "TRANSIT FARE Exampleville ON"
        assert primary["is_duplicate"] == 0

        # Verify duplicate marked
        duplicate = projection_builder.get_transaction("def456")
        assert duplicate is not None
        assert duplicate["is_duplicate"] == 1
        assert duplicate["primary_transaction_id"] == "abc123"

        # Verify get_all_transactions excludes duplicates by default
        transactions = projection_builder.get_all_transactions(include_duplicates=False)
        assert len(transactions) == 1
        assert transactions[0]["transaction_id"] == "abc123"

        # Verify can include duplicates explicitly
        all_txns = projection_builder.get_all_transactions(include_duplicates=True)
        assert len(all_txns) == 2

    def it_should_handle_duplicate_rejected_event(self, event_store, projection_builder):
        """Test that DuplicateRejected updates last_event_id but keeps transactions separate."""
        from gilt.model.events import DuplicateRejected

        # Import two transactions
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test1.csv",
            source_account="TEST_ACCT",
            raw_description="TRANSIT FARE Othertown",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event1)

        event2 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="def456",
            source_file="test2.csv",
            source_account="TEST_ACCT",
            raw_description="TRANSIT FARE Exampleville",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event2)

        # User rejects as duplicate
        event3 = DuplicateRejected(
            suggestion_event_id="suggestion-123",
            transaction_id_1="abc123",
            transaction_id_2="def456",
            user_rationale="Different cities",
            llm_was_correct=False,
        )
        event_store.append_event(event3)

        # Build projection
        projection_builder.rebuild_from_scratch(event_store)

        # Verify both transactions remain separate
        txn1 = projection_builder.get_transaction("abc123")
        txn2 = projection_builder.get_transaction("def456")

        assert txn1 is not None
        assert txn2 is not None
        assert txn1["is_duplicate"] == 0
        assert txn2["is_duplicate"] == 0
        assert txn1["primary_transaction_id"] is None
        assert txn2["primary_transaction_id"] is None

        # Verify both appear in get_all_transactions
        transactions = projection_builder.get_all_transactions()
        assert len(transactions) == 2

        # Verify last_event_id updated (tracks feedback was processed)
        assert txn1["last_event_id"] == event3.event_id
        assert txn2["last_event_id"] == event3.event_id

    def it_should_track_current_sequence_number(self, event_store, projection_builder):
        """Test that get_current_sequence returns the last processed event sequence."""
        # Initially should be 0
        assert projection_builder.get_current_sequence() == 0

        # Add some events
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="Test transaction",
            amount=Decimal("-10.00"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event1)

        event2 = TransactionImported(
            transaction_date="2025-10-16",
            transaction_id="def456",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="Test transaction 2",
            amount=Decimal("-20.00"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event2)

        # After full rebuild, should be at sequence 2
        projection_builder.rebuild_from_scratch(event_store)
        assert projection_builder.get_current_sequence() == 2

        # Add another event
        event3 = TransactionImported(
            transaction_date="2025-10-17",
            transaction_id="ghi789",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="Test transaction 3",
            amount=Decimal("-30.00"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event3)

        # After incremental rebuild, should be at sequence 3
        projection_builder.rebuild_incremental(event_store)
        assert projection_builder.get_current_sequence() == 3

    def it_should_apply_transaction_enriched_event(self, event_store, projection_builder):
        """Test that TransactionEnriched events populate enrichment columns."""
        # Import transaction
        event1 = TransactionImported(
            transaction_date="2026-02-15",
            transaction_id="abc123",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="ZOOM.US 888-799-9666",
            amount=Decimal("-30.99"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event1)

        # Enrich it
        event2 = TransactionEnriched(
            transaction_id="abc123",
            vendor="Zoom Communications, Inc.",
            service="Zoom Workplace Pro + Scheduler",
            invoice_number="INV342066242",
            tax_amount=Decimal("4.03"),
            tax_type="HST",
            currency="CAD",
            receipt_file="2026/02/Zoom-INV342066242.pdf",
            enrichment_source="receipts/zoom.json",
            source_email="noreply@zoom.us",
        )
        event_store.append_event(event2)

        # Build projection
        projection_builder.rebuild_from_scratch(event_store)

        # Verify enrichment columns
        txn = projection_builder.get_transaction("abc123")
        assert txn is not None
        assert txn["vendor"] == "Zoom Communications, Inc."
        assert txn["service"] == "Zoom Workplace Pro + Scheduler"
        assert txn["invoice_number"] == "INV342066242"
        assert txn["tax_amount"] == 4.03
        assert txn["tax_type"] == "HST"
        assert txn["enrichment_currency"] == "CAD"
        assert txn["receipt_file"] == "2026/02/Zoom-INV342066242.pdf"
        assert txn["enrichment_source"] == "receipts/zoom.json"
        assert txn["source_email"] == "noreply@zoom.us"

        # Original description should be preserved
        assert txn["canonical_description"] == "ZOOM.US 888-799-9666"

    def it_should_use_latest_enrichment_when_multiple_exist(self, event_store, projection_builder):
        """Test that latest enrichment wins for the same transaction."""
        # Import transaction
        event1 = TransactionImported(
            transaction_date="2026-02-15",
            transaction_id="abc123",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="ZOOM.US 888-799-9666",
            amount=Decimal("-30.99"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event1)

        # First enrichment
        event2 = TransactionEnriched(
            transaction_id="abc123",
            vendor="Zoom Video Communications",
            enrichment_source="receipts/zoom-v1.json",
        )
        event_store.append_event(event2)

        # Second (corrected) enrichment
        event3 = TransactionEnriched(
            transaction_id="abc123",
            vendor="Zoom Communications, Inc.",
            service="Zoom Workplace Pro",
            invoice_number="INV342066242",
            enrichment_source="receipts/zoom-v2.json",
        )
        event_store.append_event(event3)

        # Build projection
        projection_builder.rebuild_from_scratch(event_store)

        # Latest enrichment should win
        txn = projection_builder.get_transaction("abc123")
        assert txn["vendor"] == "Zoom Communications, Inc."
        assert txn["service"] == "Zoom Workplace Pro"
        assert txn["invoice_number"] == "INV342066242"
        assert txn["enrichment_source"] == "receipts/zoom-v2.json"

    def it_should_leave_enrichment_columns_null_when_not_enriched(self, event_store, projection_builder):
        """Test that unenriched transactions have null enrichment columns."""
        event = TransactionImported(
            transaction_date="2026-02-15",
            transaction_id="abc123",
            source_file="test.csv",
            source_account="TEST_ACCT",
            raw_description="GROCERY STORE",
            amount=Decimal("-50.00"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event)

        projection_builder.rebuild_from_scratch(event_store)

        txn = projection_builder.get_transaction("abc123")
        assert txn["vendor"] is None
        assert txn["service"] is None
        assert txn["invoice_number"] is None
        assert txn["tax_amount"] is None
        assert txn["receipt_file"] is None
