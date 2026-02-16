"""
Tests for event store.
"""

from decimal import Decimal
from pathlib import Path
import tempfile

import pytest

from gilt.model.events import (
    TransactionImported,
    DuplicateSuggested,
    TransactionCategorized,
)
from gilt.storage.event_store import EventStore


class DescribeEventStore:
    """Test EventStore functionality."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        # Cleanup
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def event_store(self, temp_db_path):
        """Create an EventStore instance with temporary database."""
        return EventStore(str(temp_db_path))

    def it_should_initialize_database_schema(self, event_store):
        """Should create tables on initialization."""
        # Verify we can query the events table
        events = event_store.get_all_events()
        assert events == []

    def it_should_append_event(self, event_store):
        """Should append an event to the store."""
        event = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="test.csv",
            source_account="TEST",
            raw_description="Test transaction",
            amount=Decimal("-10.00"),
            currency="CAD",
            raw_data={},
        )
        event_store.append_event(event)

        events = event_store.get_all_events()
        assert len(events) == 1
        assert events[0].transaction_id == "abc123"

    def it_should_append_multiple_events(self, event_store):
        """Should append multiple events in order."""
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="txn1",
            source_file="test.csv",
            source_account="TEST",
            raw_description="Transaction 1",
            amount=Decimal("-10.00"),
            currency="CAD",
            raw_data={},
        )
        event2 = TransactionImported(
            transaction_date="2025-10-16",
            transaction_id="txn2",
            source_file="test.csv",
            source_account="TEST",
            raw_description="Transaction 2",
            amount=Decimal("-20.00"),
            currency="CAD",
            raw_data={},
        )

        event_store.append_event(event1)
        event_store.append_event(event2)

        events = event_store.get_all_events()
        assert len(events) == 2
        assert events[0].transaction_id == "txn1"
        assert events[1].transaction_id == "txn2"

    def it_should_get_events_by_aggregate_id(self, event_store):
        """Should retrieve events for a specific aggregate."""
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="txn1",
            source_file="test.csv",
            source_account="TEST",
            raw_description="Transaction 1",
            amount=Decimal("-10.00"),
            currency="CAD",
            raw_data={},
        )
        event2 = TransactionCategorized(
            transaction_id="txn1", category="Test Category", source="user"
        )
        event3 = TransactionImported(
            transaction_date="2025-10-16",
            transaction_id="txn2",
            source_file="test.csv",
            source_account="TEST",
            raw_description="Transaction 2",
            amount=Decimal("-20.00"),
            currency="CAD",
            raw_data={},
        )

        event_store.append_event(event1)
        event_store.append_event(event2)
        event_store.append_event(event3)

        txn1_events = event_store.get_events("transaction", "txn1")
        assert len(txn1_events) == 2
        assert txn1_events[0].event_type == "TransactionImported"
        assert txn1_events[1].event_type == "TransactionCategorized"

    def it_should_get_events_by_type(self, event_store):
        """Should retrieve events of a specific type."""
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="txn1",
            source_file="test.csv",
            source_account="TEST",
            raw_description="Transaction 1",
            amount=Decimal("-10.00"),
            currency="CAD",
            raw_data={},
        )
        event2 = TransactionCategorized(
            transaction_id="txn1", category="Test Category", source="user"
        )
        event3 = TransactionImported(
            transaction_date="2025-10-16",
            transaction_id="txn2",
            source_file="test.csv",
            source_account="TEST",
            raw_description="Transaction 2",
            amount=Decimal("-20.00"),
            currency="CAD",
            raw_data={},
        )

        event_store.append_event(event1)
        event_store.append_event(event2)
        event_store.append_event(event3)

        import_events = event_store.get_events_by_type("TransactionImported")
        assert len(import_events) == 2

        categorize_events = event_store.get_events_by_type("TransactionCategorized")
        assert len(categorize_events) == 1

    def it_should_maintain_event_sequence(self, event_store):
        """Should maintain sequential event ordering."""
        events = []
        for i in range(5):
            event = TransactionImported(
                transaction_date=f"2025-10-{15 + i:02d}",
                transaction_id=f"txn{i}",
                source_file="test.csv",
                source_account="TEST",
                raw_description=f"Transaction {i}",
                amount=Decimal(f"-{10 + i}.00"),
                currency="CAD",
                raw_data={},
            )
            events.append(event)
            event_store.append_event(event)

        retrieved = event_store.get_all_events()
        assert len(retrieved) == 5
        for i, event in enumerate(retrieved):
            assert event.transaction_id == f"txn{i}"

    def it_should_preserve_event_immutability(self, event_store):
        """Events should be immutable after storage."""
        event = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="txn1",
            source_file="test.csv",
            source_account="TEST",
            raw_description="Original",
            amount=Decimal("-10.00"),
            currency="CAD",
            raw_data={"original": "data"},
        )
        event_store.append_event(event)

        # Retrieve and verify
        retrieved = event_store.get_all_events()[0]
        assert retrieved.raw_description == "Original"
        assert retrieved.raw_data == {"original": "data"}

    def it_should_support_different_event_types(self, event_store):
        """Should store and retrieve different event types."""
        event1 = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="txn1",
            source_file="test.csv",
            source_account="TEST",
            raw_description="Transaction 1",
            amount=Decimal("-10.00"),
            currency="CAD",
            raw_data={},
        )
        event2 = DuplicateSuggested(
            transaction_id_1="txn1",
            transaction_id_2="txn2",
            confidence=0.92,
            reasoning="Similar transactions",
            model="test-model",
            prompt_version="v1",
            assessment={"is_duplicate": True},
        )

        event_store.append_event(event1)
        event_store.append_event(event2)

        all_events = event_store.get_all_events()
        assert len(all_events) == 2
        assert isinstance(all_events[0], TransactionImported)
        assert isinstance(all_events[1], DuplicateSuggested)

    def it_should_handle_empty_store(self, event_store):
        """Should handle queries on empty store."""
        assert event_store.get_all_events() == []
        assert event_store.get_events("transaction", "nonexistent") == []
        assert event_store.get_events_by_type("TransactionImported") == []

    def it_should_get_events_since_sequence(self, event_store):
        """Should retrieve events after a specific sequence number."""
        for i in range(5):
            event = TransactionImported(
                transaction_date=f"2025-10-{15 + i:02d}",
                transaction_id=f"txn{i}",
                source_file="test.csv",
                source_account="TEST",
                raw_description=f"Transaction {i}",
                amount=Decimal(f"-{10 + i}.00"),
                currency="CAD",
                raw_data={},
            )
            event_store.append_event(event)

        # Get events after sequence 2
        recent_events = event_store.get_events_since(2)
        assert len(recent_events) == 3
        assert recent_events[0].transaction_id == "txn2"
        assert recent_events[1].transaction_id == "txn3"
        assert recent_events[2].transaction_id == "txn4"
