"""
Tests for budget projection builder and event sourcing.

Validates budget event replay, historical queries, and time-travel capabilities.
"""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path
from datetime import datetime, date, timedelta
from uuid import uuid4

import pytest

from gilt.model.events import BudgetCreated, BudgetUpdated, BudgetDeleted
from gilt.storage.event_store import EventStore
from gilt.storage.budget_projection import BudgetProjectionBuilder, BudgetProjection


class DescribeBudgetProjectionBuilder:
    """Test suite for budget projection builder."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def event_store_db(self):
        """Create temporary event store database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def event_store(self, event_store_db):
        """Create event store instance."""
        return EventStore(event_store_db)

    @pytest.fixture
    def builder(self, temp_db):
        """Create budget projection builder instance."""
        return BudgetProjectionBuilder(temp_db)

    def it_should_create_schema_on_initialization(self, temp_db):
        """Test that database schema is created on init."""
        BudgetProjectionBuilder(temp_db)

        import sqlite3

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='budget_projections'"
        )
        assert cursor.fetchone() is not None

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='budget_history'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def it_should_apply_budget_created_event(self, builder, event_store):
        """Test that BudgetCreated event creates a projection."""
        # Arrange
        budget_id = str(uuid4())
        event = BudgetCreated(
            budget_id=budget_id,
            category="Transportation",
            subcategory="Public Transit",
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("200.00"),
            currency="CAD",
        )
        event_store.append_event(event)

        # Act
        builder.rebuild_from_scratch(event_store)

        # Assert
        projection = builder.get_budget(budget_id)
        assert projection is not None
        assert projection.budget_id == budget_id
        assert projection.category == "Transportation"
        assert projection.subcategory == "Public Transit"
        assert projection.amount == Decimal("200.00")
        assert projection.period_type == "monthly"
        assert projection.start_date == "2025-01-01"
        assert not projection.is_deleted

    def it_should_apply_budget_updated_event(self, builder, event_store):
        """Test that BudgetUpdated event modifies projection."""
        # Arrange
        budget_id = str(uuid4())
        created = BudgetCreated(
            budget_id=budget_id,
            category="Housing",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("1500.00"),
            currency="CAD",
        )
        updated = BudgetUpdated(
            budget_id=budget_id,
            category="Housing",
            subcategory=None,
            new_amount=Decimal("1600.00"),
            previous_amount=Decimal("1500.00"),
            currency="CAD",
        )
        event_store.append_event(created)
        event_store.append_event(updated)

        # Act
        builder.rebuild_from_scratch(event_store)

        # Assert
        projection = builder.get_budget(budget_id)
        assert projection is not None
        assert projection.amount == Decimal("1600.00")

    def it_should_apply_budget_deleted_event(self, builder, event_store):
        """Test that BudgetDeleted event marks projection as deleted."""
        # Arrange
        budget_id = str(uuid4())
        created = BudgetCreated(
            budget_id=budget_id,
            category="Entertainment",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("100.00"),
            currency="CAD",
        )
        deleted = BudgetDeleted(
            budget_id=budget_id,
            category="Entertainment",
            subcategory=None,
            final_amount=Decimal("100.00"),
            final_period_type="monthly",
            final_start_date="2025-01-01",
            currency="CAD",
        )
        event_store.append_event(created)
        event_store.append_event(deleted)

        # Act
        builder.rebuild_from_scratch(event_store)

        # Assert
        projection = builder.get_budget(budget_id)
        assert projection is not None
        assert projection.is_deleted

    def it_should_track_budget_history(self, builder, event_store):
        """Test that budget changes are tracked in history."""
        # Arrange
        budget_id = str(uuid4())
        created = BudgetCreated(
            budget_id=budget_id,
            category="Food",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("500.00"),
            currency="CAD",
        )
        updated = BudgetUpdated(
            budget_id=budget_id,
            category="Food",
            subcategory=None,
            new_amount=Decimal("550.00"),
            previous_amount=Decimal("500.00"),
            currency="CAD",
        )
        event_store.append_event(created)
        event_store.append_event(updated)

        # Act
        builder.rebuild_from_scratch(event_store)

        # Assert
        history = builder.get_budget_history(budget_id)
        assert len(history) == 2
        assert history[0]["event_type"] == "BudgetCreated"
        assert history[0]["amount"] == 500.00
        assert history[1]["event_type"] == "BudgetUpdated"
        assert history[1]["amount"] == 550.00

    def it_should_get_active_budgets(self, builder, event_store):
        """Test retrieving only active (non-deleted) budgets."""
        # Arrange
        budget1_id = str(uuid4())
        budget2_id = str(uuid4())

        created1 = BudgetCreated(
            budget_id=budget1_id,
            category="Transportation",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("200.00"),
            currency="CAD",
        )
        created2 = BudgetCreated(
            budget_id=budget2_id,
            category="Housing",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("1500.00"),
            currency="CAD",
        )
        deleted2 = BudgetDeleted(
            budget_id=budget2_id,
            category="Housing",
            subcategory=None,
            final_amount=Decimal("1500.00"),
            final_period_type="monthly",
            final_start_date="2025-01-01",
            currency="CAD",
        )

        event_store.append_event(created1)
        event_store.append_event(created2)
        event_store.append_event(deleted2)

        # Act
        builder.rebuild_from_scratch(event_store)
        active_budgets = builder.get_active_budgets()

        # Assert
        assert len(active_budgets) == 1
        assert active_budgets[0].budget_id == budget1_id
        assert active_budgets[0].category == "Transportation"

    def it_should_filter_active_budgets_by_category(self, builder, event_store):
        """Test filtering active budgets by category."""
        # Arrange
        budget1_id = str(uuid4())
        budget2_id = str(uuid4())

        created1 = BudgetCreated(
            budget_id=budget1_id,
            category="Transportation",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("200.00"),
            currency="CAD",
        )
        created2 = BudgetCreated(
            budget_id=budget2_id,
            category="Housing",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("1500.00"),
            currency="CAD",
        )

        event_store.append_event(created1)
        event_store.append_event(created2)

        # Act
        builder.rebuild_from_scratch(event_store)
        transport_budgets = builder.get_active_budgets(category="Transportation")

        # Assert
        assert len(transport_budgets) == 1
        assert transport_budgets[0].category == "Transportation"

    def it_should_support_time_travel_queries(self, builder, event_store):
        """Test querying budget state at a specific historical date."""
        # Arrange
        budget_id = str(uuid4())
        base_time = datetime(2025, 1, 1, 10, 0, 0)

        # Create budget on Jan 1
        created = BudgetCreated(
            budget_id=budget_id,
            category="Food",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("400.00"),
            currency="CAD",
        )
        created.event_timestamp = base_time
        event_store.append_event(created)

        # Update budget on Feb 1
        updated = BudgetUpdated(
            budget_id=budget_id,
            category="Food",
            subcategory=None,
            new_amount=Decimal("450.00"),
            previous_amount=Decimal("400.00"),
            new_start_date="2025-02-01",
            previous_start_date="2025-01-01",
            currency="CAD",
        )
        updated.event_timestamp = base_time + timedelta(days=31)
        event_store.append_event(updated)

        # Delete budget on Mar 1
        deleted = BudgetDeleted(
            budget_id=budget_id,
            category="Food",
            subcategory=None,
            final_amount=Decimal("450.00"),
            final_period_type="monthly",
            final_start_date="2025-02-01",
            currency="CAD",
        )
        deleted.event_timestamp = base_time + timedelta(days=59)
        event_store.append_event(deleted)

        # Act
        builder.rebuild_from_scratch(event_store)

        # Query state at Jan 15 (should have original budget)
        jan_budgets = builder.get_budgets_at_date(date(2025, 1, 15))
        assert len(jan_budgets) == 1
        assert jan_budgets[0].amount == Decimal("400.00")
        assert jan_budgets[0].start_date == "2025-01-01"

        # Query state at Feb 15 (should have updated budget)
        feb_budgets = builder.get_budgets_at_date(date(2025, 2, 15))
        assert len(feb_budgets) == 1
        assert feb_budgets[0].amount == Decimal("450.00")
        assert feb_budgets[0].start_date == "2025-02-01"

        # Query state at Mar 15 (should have no budget - deleted)
        mar_budgets = builder.get_budgets_at_date(date(2025, 3, 15))
        assert len(mar_budgets) == 0

    def it_should_handle_multiple_budget_updates(self, builder, event_store):
        """Test multiple updates to the same budget."""
        # Arrange
        budget_id = str(uuid4())
        base_time = datetime(2025, 1, 1, 10, 0, 0)

        created = BudgetCreated(
            budget_id=budget_id,
            category="Utilities",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("100.00"),
            currency="CAD",
        )
        created.event_timestamp = base_time

        update1 = BudgetUpdated(
            budget_id=budget_id,
            category="Utilities",
            subcategory=None,
            new_amount=Decimal("110.00"),
            previous_amount=Decimal("100.00"),
            currency="CAD",
        )
        update1.event_timestamp = base_time + timedelta(days=10)

        update2 = BudgetUpdated(
            budget_id=budget_id,
            category="Utilities",
            subcategory=None,
            new_amount=Decimal("120.00"),
            previous_amount=Decimal("110.00"),
            currency="CAD",
        )
        update2.event_timestamp = base_time + timedelta(days=20)

        event_store.append_event(created)
        event_store.append_event(update1)
        event_store.append_event(update2)

        # Act
        builder.rebuild_from_scratch(event_store)

        # Assert
        projection = builder.get_budget(budget_id)
        assert projection.amount == Decimal("120.00")

        history = builder.get_budget_history(budget_id)
        assert len(history) == 3
        assert history[0]["amount"] == 100.00
        assert history[1]["amount"] == 110.00
        assert history[2]["amount"] == 120.00

    def it_should_be_idempotent_on_duplicate_events(self, builder, event_store):
        """Test that replaying same events produces same result."""
        # Arrange
        budget_id = str(uuid4())
        event = BudgetCreated(
            budget_id=budget_id,
            category="Healthcare",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("150.00"),
            currency="CAD",
        )
        event_store.append_event(event)

        # Act - rebuild twice
        builder.rebuild_from_scratch(event_store)
        projection1 = builder.get_budget(budget_id)

        builder.rebuild_from_scratch(event_store)
        projection2 = builder.get_budget(budget_id)

        # Assert - same result
        assert projection1.to_dict() == projection2.to_dict()

    def it_should_handle_period_type_changes(self, builder, event_store):
        """Test updating budget period type (monthly to yearly)."""
        # Arrange
        budget_id = str(uuid4())
        created = BudgetCreated(
            budget_id=budget_id,
            category="Savings",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("500.00"),
            currency="CAD",
        )
        updated = BudgetUpdated(
            budget_id=budget_id,
            category="Savings",
            subcategory=None,
            new_period_type="yearly",
            previous_period_type="monthly",
            new_amount=Decimal("6000.00"),
            previous_amount=Decimal("500.00"),
            currency="CAD",
        )

        event_store.append_event(created)
        event_store.append_event(updated)

        # Act
        builder.rebuild_from_scratch(event_store)

        # Assert
        projection = builder.get_budget(budget_id)
        assert projection.period_type == "yearly"
        assert projection.amount == Decimal("6000.00")

    def it_should_preserve_history_after_deletion(self, builder, event_store):
        """Test that budget history is preserved after deletion."""
        # Arrange
        budget_id = str(uuid4())
        created = BudgetCreated(
            budget_id=budget_id,
            category="Education",
            subcategory=None,
            period_type="monthly",
            start_date="2025-01-01",
            amount=Decimal("300.00"),
            currency="CAD",
        )
        deleted = BudgetDeleted(
            budget_id=budget_id,
            category="Education",
            subcategory=None,
            final_amount=Decimal("300.00"),
            final_period_type="monthly",
            final_start_date="2025-01-01",
            currency="CAD",
            rationale="No longer needed",
        )

        event_store.append_event(created)
        event_store.append_event(deleted)

        # Act
        builder.rebuild_from_scratch(event_store)

        # Assert
        projection = builder.get_budget(budget_id)
        assert projection.is_deleted

        # History should still be available
        history = builder.get_budget_history(budget_id)
        assert len(history) == 2
        assert history[0]["event_type"] == "BudgetCreated"
        assert history[1]["event_type"] == "BudgetDeleted"


class DescribeBudgetProjection:
    """Test suite for BudgetProjection model."""

    def it_should_convert_to_dict(self):
        """Test that BudgetProjection can be serialized to dict."""
        # Arrange
        projection = BudgetProjection(
            budget_id="test-123",
            category="Transportation",
            subcategory="Public Transit",
            amount=Decimal("200.00"),
            period_type="monthly",
            start_date="2025-01-01",
            currency="CAD",
            is_deleted=False,
            created_at=datetime(2025, 1, 1, 10, 0, 0),
            updated_at=datetime(2025, 1, 1, 10, 0, 0),
            last_event_id="event-456",
        )

        # Act
        result = projection.to_dict()

        # Assert
        assert result["budget_id"] == "test-123"
        assert result["category"] == "Transportation"
        assert result["subcategory"] == "Public Transit"
        assert result["amount"] == "200.00"
        assert result["period_type"] == "monthly"
        assert result["start_date"] == "2025-01-01"
        assert result["currency"] == "CAD"
        assert result["is_deleted"] is False
        assert result["last_event_id"] == "event-456"
