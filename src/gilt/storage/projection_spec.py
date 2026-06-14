"""
Tests for transaction projection builder.

These tests verify that projections can be correctly built from events
and that the rebuild process is idempotent and accurate.
"""

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from gilt.model.events import (
    DuplicateConfirmed,
    TransactionCategorized,
    TransactionDescriptionObserved,
    TransactionEnriched,
    TransactionImported,
)
from gilt.storage.event_store import EventStore
from gilt.storage.projection import (
    DuplicateCorrection,
    DuplicateGroupState,
    ProjectionBuilder,
    build_duplicate_corrections,
    find_root_primary,
)


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
        processed = projection_builder.build_from_scratch(event_store)
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
        projection_builder.build_from_scratch(event_store)

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
        projection_builder.build_from_scratch(event_store)

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
        projection_builder.build_from_scratch(event_store)

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
        projection_builder.build_from_scratch(event_store)

        # Verify categorization
        txn = projection_builder.get_transaction("abc123")
        assert txn is not None
        assert txn["category"] == "Transportation"
        assert txn["subcategory"] == "Public Transit"

    def it_should_build_incrementally(self, event_store, projection_builder):
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
        processed = projection_builder.build_from_scratch(event_store)
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
        processed = projection_builder.build_incremental(event_store)
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
        projection_builder.build_from_scratch(event_store)

        # Try incremental rebuild with no new events
        processed = projection_builder.build_incremental(event_store)
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
        projection_builder.build_from_scratch(event_store)

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
        projection_builder.build_from_scratch(event_store)

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
        projection_builder.build_from_scratch(event_store)

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
        projection_builder.build_from_scratch(event_store)
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
        projection_builder.build_incremental(event_store)
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
        projection_builder.build_from_scratch(event_store)

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
        projection_builder.build_from_scratch(event_store)

        # Latest enrichment should win
        txn = projection_builder.get_transaction("abc123")
        assert txn["vendor"] == "Zoom Communications, Inc."
        assert txn["service"] == "Zoom Workplace Pro"
        assert txn["invoice_number"] == "INV342066242"
        assert txn["enrichment_source"] == "receipts/zoom-v2.json"

    def it_should_leave_enrichment_columns_null_when_not_enriched(
        self, event_store, projection_builder
    ):
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

        projection_builder.build_from_scratch(event_store)

        txn = projection_builder.get_transaction("abc123")
        assert txn["vendor"] is None
        assert txn["service"] is None
        assert txn["invoice_number"] is None
        assert txn["tax_amount"] is None
        assert txn["receipt_file"] is None

    def it_should_delete_account_projections(self, event_store, projection_builder):
        """Should remove all projection rows for a given account_id."""
        for i in range(3):
            event = TransactionImported(
                transaction_date=f"2025-01-{10 + i:02d}",
                transaction_id=f"txn{i:012d}",
                source_file="test.csv",
                source_account="MYBANK_CHQ",
                raw_description="EXAMPLE UTILITY",
                amount=Decimal("-50.00"),
                currency="CAD",
                raw_data={},
            )
            event_store.append_event(event)

        projection_builder.build_from_scratch(event_store)
        assert len(projection_builder.get_all_transactions()) == 3

        deleted = projection_builder.delete_account_projections("MYBANK_CHQ")
        assert deleted == 3
        assert len(projection_builder.get_all_transactions()) == 0

    def it_should_return_distinct_non_duplicate_account_ids(self, event_store, projection_builder):
        for account_id, txn_id in [
            ("MYBANK_CHQ", "txn000000000001"),
            ("MYBANK_CHQ", "txn000000000002"),
            ("BANK2_BIZ", "txn000000000003"),
        ]:
            event_store.append_event(
                TransactionImported(
                    transaction_date="2025-01-10",
                    transaction_id=txn_id,
                    source_file="test.csv",
                    source_account=account_id,
                    raw_description="EXAMPLE UTILITY",
                    amount=Decimal("-50.00"),
                    currency="CAD",
                    raw_data={},
                )
            )
        projection_builder.build_from_scratch(event_store)

        account_ids = projection_builder.get_distinct_account_ids()
        assert account_ids == ["BANK2_BIZ", "MYBANK_CHQ"]

    def it_should_reset_projection_metadata(self, event_store, projection_builder):
        """Should clear the projection_metadata table so incremental rebuild replays all events."""
        event = TransactionImported(
            transaction_date="2025-01-10",
            transaction_id="txn000000000001",
            source_file="test.csv",
            source_account="MYBANK_CHQ",
            raw_description="SAMPLE STORE",
            amount=Decimal("-25.00"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event)
        projection_builder.build_from_scratch(event_store)

        # Sequence should be stored
        assert projection_builder.get_current_sequence() > 0

        projection_builder.reset_metadata()
        assert projection_builder.get_current_sequence() == 0

    def it_should_not_leave_orphan_when_duplicate_pair_is_confirmed_in_both_directions(
        self, event_store, projection_builder
    ):
        """Both-direction DuplicateConfirmed events must not leave an orphan group."""
        for txn_id, desc in [
            ("t1000000000001", "SAMPLE STORE A"),
            ("t2000000000002", "SAMPLE STORE B"),
        ]:
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

        # Confirm T1 as primary of T2, then T2 as primary of T1 (cycle)
        event_store.append_event(
            DuplicateConfirmed(
                suggestion_event_id="sug-001",
                primary_transaction_id="t1000000000001",
                duplicate_transaction_id="t2000000000002",
                canonical_description="SAMPLE STORE A",
                user_rationale="test",
                llm_was_correct=True,
            )
        )
        event_store.append_event(
            DuplicateConfirmed(
                suggestion_event_id="sug-002",
                primary_transaction_id="t2000000000002",
                duplicate_transaction_id="t1000000000001",
                canonical_description="SAMPLE STORE B",
                user_rationale="test",
                llm_was_correct=True,
            )
        )

        projection_builder.build_from_scratch(event_store)

        t1 = projection_builder.get_transaction("t1000000000001")
        t2 = projection_builder.get_transaction("t2000000000002")
        assert t1 is not None
        assert t2 is not None

        # Exactly one must be the primary (is_duplicate=0) and one the duplicate
        primaries = [t for t in [t1, t2] if t["is_duplicate"] == 0]
        duplicates = [t for t in [t1, t2] if t["is_duplicate"] == 1]
        assert len(primaries) == 1, "Expected exactly one primary"
        assert len(duplicates) == 1, "Expected exactly one duplicate"
        assert duplicates[0]["primary_transaction_id"] == primaries[0]["transaction_id"]

    def it_should_chain_resolve_stale_primary_when_marking_duplicate(
        self, event_store, projection_builder
    ):
        """Confirming (T3, T1) after (T1, T2) should result in T3 being primary for both T1 and T2."""
        for txn_id, desc in [
            ("t1000000000001", "ACME CORP A"),
            ("t2000000000002", "ACME CORP B"),
            ("t3000000000003", "ACME CORP C"),
        ]:
            event_store.append_event(
                TransactionImported(
                    transaction_date="2025-02-01",
                    transaction_id=txn_id,
                    source_file="test.csv",
                    source_account="MYBANK_CHQ",
                    raw_description=desc,
                    amount=Decimal("-75.00"),
                    currency="CAD",
                    raw_data={},
                )
            )

        # T1 is primary, T2 is dup of T1
        event_store.append_event(
            DuplicateConfirmed(
                suggestion_event_id="sug-001",
                primary_transaction_id="t1000000000001",
                duplicate_transaction_id="t2000000000002",
                canonical_description="ACME CORP A",
                user_rationale="test",
                llm_was_correct=True,
            )
        )
        # T3 is primary, T1 is dup of T3 (T1 is itself a dup, so T2 should get re-rooted)
        event_store.append_event(
            DuplicateConfirmed(
                suggestion_event_id="sug-002",
                primary_transaction_id="t3000000000003",
                duplicate_transaction_id="t1000000000001",
                canonical_description="ACME CORP C",
                user_rationale="test",
                llm_was_correct=True,
            )
        )

        projection_builder.build_from_scratch(event_store)

        t1 = projection_builder.get_transaction("t1000000000001")
        t2 = projection_builder.get_transaction("t2000000000002")
        t3 = projection_builder.get_transaction("t3000000000003")

        assert t3["is_duplicate"] == 0
        assert t1["is_duplicate"] == 1
        assert t1["primary_transaction_id"] == "t3000000000003"
        # T2 must not point at a duplicate (T1); normaliser should have re-rooted it to T3
        assert t2["is_duplicate"] == 1
        assert t2["primary_transaction_id"] == "t3000000000003"

    def it_should_ignore_self_referential_duplicate_confirmations(
        self, event_store, projection_builder
    ):
        """A DuplicateConfirmed where primary == duplicate must not alter is_duplicate."""
        event_store.append_event(
            TransactionImported(
                transaction_date="2025-03-01",
                transaction_id="t1000000000001",
                source_file="test.csv",
                source_account="MYBANK_CHQ",
                raw_description="EXAMPLE UTILITY",
                amount=Decimal("-30.00"),
                currency="CAD",
                raw_data={},
            )
        )
        # Self-referential confirmation
        event_store.append_event(
            DuplicateConfirmed(
                suggestion_event_id="sug-001",
                primary_transaction_id="t1000000000001",
                duplicate_transaction_id="t1000000000001",
                canonical_description="EXAMPLE UTILITY",
                user_rationale="test",
                llm_was_correct=False,
            )
        )

        projection_builder.build_from_scratch(event_store)

        t1 = projection_builder.get_transaction("t1000000000001")
        assert t1 is not None
        assert t1["is_duplicate"] == 0
        assert t1["primary_transaction_id"] is None

    def it_should_normalize_existing_orphans_on_rebuild(
        self, event_store, projection_builder, temp_dir
    ):
        """Projection DB with an orphan cycle (both-direction confirms) is repaired on rebuild.

        This exercises _normalize_duplicate_groups by using events that create the
        cycle (same scenario as the both-directions test) and then doing a second
        build_from_scratch — confirming the normaliser fires on every full rebuild.
        """
        for txn_id, desc in [
            ("t1000000000001", "SAMPLE STORE X"),
            ("t2000000000002", "SAMPLE STORE Y"),
        ]:
            event_store.append_event(
                TransactionImported(
                    transaction_date="2025-04-01",
                    transaction_id=txn_id,
                    source_file="test.csv",
                    source_account="MYBANK_CHQ",
                    raw_description=desc,
                    amount=Decimal("-20.00"),
                    currency="CAD",
                    raw_data={},
                )
            )

        # Add cycle-creating events: T1→T2, then T2→T1
        event_store.append_event(
            DuplicateConfirmed(
                suggestion_event_id="sug-001",
                primary_transaction_id="t1000000000001",
                duplicate_transaction_id="t2000000000002",
                canonical_description="SAMPLE STORE X",
                user_rationale="test",
                llm_was_correct=True,
            )
        )
        event_store.append_event(
            DuplicateConfirmed(
                suggestion_event_id="sug-002",
                primary_transaction_id="t2000000000002",
                duplicate_transaction_id="t1000000000001",
                canonical_description="SAMPLE STORE Y",
                user_rationale="test",
                llm_was_correct=True,
            )
        )

        # Build twice to confirm normaliser is idempotent
        projection_builder.build_from_scratch(event_store)
        projection_builder.build_from_scratch(event_store)

        t1 = projection_builder.get_transaction("t1000000000001")
        t2 = projection_builder.get_transaction("t2000000000002")

        primaries = [t for t in [t1, t2] if t["is_duplicate"] == 0]
        duplicates = [t for t in [t1, t2] if t["is_duplicate"] == 1]
        assert len(primaries) == 1
        assert len(duplicates) == 1
        assert duplicates[0]["primary_transaction_id"] == primaries[0]["transaction_id"]


class DescribePlanDuplicateCorrections:
    """Pure-function tests for build_duplicate_corrections — no DB required."""

    def it_should_return_empty_list_for_empty_state(self):
        state = DuplicateGroupState(dup_rows=[], non_dup_ids=set())
        assert build_duplicate_corrections(state) == []

    def it_should_return_empty_list_when_no_duplicate_members_in_any_component(self):
        # Two non-dup ids, no dup_rows — nothing to fix
        state = DuplicateGroupState(dup_rows=[], non_dup_ids={"aaa", "bbb"})
        assert build_duplicate_corrections(state) == []

    def it_should_repoint_stale_chain_to_lexicographically_smallest_non_dup_root(self):
        # aaa is non-dup, bbb is dup pointing at aaa — already correct but still emits repoint
        state = DuplicateGroupState(
            dup_rows=[("bbb", "aaa")],
            non_dup_ids={"aaa"},
        )
        corrections = build_duplicate_corrections(state)
        assert len(corrections) == 1
        assert corrections[0] == DuplicateCorrection(kind="repoint", txn_id="bbb", primary_id="aaa")

    def it_should_repoint_stale_chain_to_smallest_non_dup_when_multiple_non_dups_in_component(self):
        # ccc is dup pointing at bbb (non-dup), but aaa is also non-dup in same component
        state = DuplicateGroupState(
            dup_rows=[("ccc", "bbb")],
            non_dup_ids={"aaa", "bbb"},
        )
        # aaa and bbb are unconnected non-dups — different components; only bbb+ccc are linked
        corrections = build_duplicate_corrections(state)
        assert any(
            c.kind == "repoint" and c.txn_id == "ccc" and c.primary_id == "bbb" for c in corrections
        )

    def it_should_elect_min_id_and_demote_others_for_orphan_cycle(self):
        # Both t2 and t1 are duplicates with no non-dup member — orphan cycle
        state = DuplicateGroupState(
            dup_rows=[("t2", "t1"), ("t1", "t2")],
            non_dup_ids=set(),
        )
        corrections = build_duplicate_corrections(state)
        kinds = {c.kind for c in corrections}
        assert "elect_primary" in kinds
        assert "demote" in kinds

        elected = next(c for c in corrections if c.kind == "elect_primary")
        demoted = [c for c in corrections if c.kind == "demote"]

        assert elected.txn_id == min("t1", "t2")
        assert all(c.primary_id == elected.txn_id for c in demoted)
        assert all(c.txn_id != elected.txn_id for c in demoted)

    def it_should_handle_three_member_orphan_cycle(self):
        state = DuplicateGroupState(
            dup_rows=[("t2", "t1"), ("t3", "t1"), ("t1", "t3")],
            non_dup_ids=set(),
        )
        corrections = build_duplicate_corrections(state)
        elected = next(c for c in corrections if c.kind == "elect_primary")
        demotions = [c for c in corrections if c.kind == "demote"]
        assert elected.txn_id == "t1"  # lexicographically smallest
        assert len(demotions) == 2
        assert {c.txn_id for c in demotions} == {"t2", "t3"}


class DescribeFindRootPrimary:
    """Pure-function tests for find_root_primary — no DB required."""

    def _make_lookup(self, rows: dict[str, tuple[bool, str | None]]):
        """Build a dict-backed lookup callable."""

        def lookup(txn_id: str) -> tuple[bool, str | None] | None:
            return rows.get(txn_id)

        return lookup

    def it_should_return_txn_id_when_it_is_not_a_duplicate(self):
        lookup = self._make_lookup({"aaa": (False, None)})
        root, visited = find_root_primary(lookup, "aaa")
        assert root == "aaa"
        assert "aaa" in visited

    def it_should_follow_chain_to_non_duplicate_root(self):
        lookup = self._make_lookup(
            {
                "dup1": (True, "dup2"),
                "dup2": (True, "root"),
                "root": (False, None),
            }
        )
        root, visited = find_root_primary(lookup, "dup1")
        assert root == "root"
        assert visited == ["dup1", "dup2", "root"]

    def it_should_return_none_when_row_not_found(self):
        lookup = self._make_lookup({})
        root, _ = find_root_primary(lookup, "missing")
        assert root is None

    def it_should_return_none_on_cycle_detection(self):
        lookup = self._make_lookup(
            {
                "t1": (True, "t2"),
                "t2": (True, "t1"),
            }
        )
        root, visited = find_root_primary(lookup, "t1")
        assert root is None

    def it_should_return_none_on_dead_end(self):
        # is_duplicate=True but no primary_id
        lookup = self._make_lookup({"t1": (True, None)})
        root, _ = find_root_primary(lookup, "t1")
        assert root is None

    def it_should_return_none_when_max_hops_exceeded(self):
        # Build a long chain longer than default max_hops=8
        rows = {}
        for i in range(10):
            rows[f"t{i}"] = (True, f"t{i + 1}")
        rows["t10"] = (False, None)
        lookup = self._make_lookup(rows)
        root, _ = find_root_primary(lookup, "t0", max_hops=8)
        assert root is None  # chain is 11 hops, exceeds limit
