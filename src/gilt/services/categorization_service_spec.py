"""
Tests for categorization service - functional core for categorization operations.

Following pytest-bdd-style naming with arrange-act-assert pattern.
Tests cover:
- Category validation (valid, invalid, subcategory checks)
- Transaction matching via TransactionOperationsService
- Categorization planning with validation
- Categorization application
- Event emission for training data
- Edge cases (empty lists, invalid categories)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from gilt.model.account import Transaction, TransactionGroup
from gilt.model.category import (
    Budget,
    BudgetPeriod,
    Category,
    CategoryConfig,
    Subcategory,
)
from gilt.model.events import TransactionCategorized
from gilt.services.categorization_service import CategorizationService
from gilt.services.transaction_operations_service import SearchCriteria
from gilt.storage.event_store import EventStore


@pytest.fixture
def sample_category_config() -> CategoryConfig:
    """Sample category configuration for testing."""
    return CategoryConfig(
        categories=[
            Category(
                name="Housing",
                description="Housing expenses",
                subcategories=[
                    Subcategory(name="Rent", description="Monthly rent"),
                    Subcategory(name="Utilities", description="Utilities"),
                ],
                budget=Budget(amount=2000.0, period=BudgetPeriod.monthly),
            ),
            Category(
                name="Groceries",
                description="Food and groceries",
                budget=Budget(amount=500.0, period=BudgetPeriod.monthly),
            ),
            Category(
                name="Transportation",
                description="Transport costs",
            ),
        ]
    )


@pytest.fixture
def sample_transactions() -> list[TransactionGroup]:
    """Sample transactions for testing."""
    return [
        TransactionGroup(
            group_id="group1",
            primary=Transaction(
                transaction_id="txn00001",
                date=date(2025, 1, 15),
                description="Rent payment",
                amount=-1500.00,
                currency="CAD",
                account_id="CHQ",
            ),
        ),
        TransactionGroup(
            group_id="group2",
            primary=Transaction(
                transaction_id="txn00002",
                date=date(2025, 1, 16),
                description="SPOTIFY Premium",
                amount=-10.99,
                currency="CAD",
                account_id="MC",
            ),
        ),
        TransactionGroup(
            group_id="group3",
            primary=Transaction(
                transaction_id="txn00003",
                date=date(2025, 1, 17),
                description="Example Utility Payment",
                amount=-85.50,
                currency="CAD",
                account_id="CHQ",
            ),
        ),
        TransactionGroup(
            group_id="group4",
            primary=Transaction(
                transaction_id="txn00004",
                date=date(2025, 1, 18),
                description="SPOTIFY Premium",
                amount=-10.99,
                currency="CAD",
                account_id="MC",
                category="Entertainment",
                subcategory="Music",
            ),
        ),
    ]


class DescribeValidation:
    """Tests for category validation."""

    def it_should_validate_existing_category_without_subcategory(
        self, sample_category_config: CategoryConfig
    ):
        # Arrange
        service = CategorizationService(sample_category_config)

        # Act
        result = service.validate_category("Housing", None)

        # Assert
        assert result.is_valid
        assert len(result.errors) == 0

    def it_should_validate_existing_category_with_valid_subcategory(
        self, sample_category_config: CategoryConfig
    ):
        # Arrange
        service = CategorizationService(sample_category_config)

        # Act
        result = service.validate_category("Housing", "Rent")

        # Assert
        assert result.is_valid
        assert len(result.errors) == 0

    def it_should_reject_nonexistent_category(self, sample_category_config: CategoryConfig):
        # Arrange
        service = CategorizationService(sample_category_config)

        # Act
        result = service.validate_category("InvalidCategory", None)

        # Assert
        assert not result.is_valid
        assert len(result.errors) == 1
        assert "Category 'InvalidCategory' not found" in result.errors[0]

    def it_should_reject_nonexistent_subcategory(self, sample_category_config: CategoryConfig):
        # Arrange
        service = CategorizationService(sample_category_config)

        # Act
        result = service.validate_category("Housing", "InvalidSubcat")

        # Assert
        assert not result.is_valid
        assert len(result.errors) == 1
        assert "Subcategory 'InvalidSubcat' not found in category 'Housing'" in result.errors[0]

    def it_should_reject_subcategory_when_category_has_none(
        self, sample_category_config: CategoryConfig
    ):
        # Arrange
        service = CategorizationService(sample_category_config)

        # Act - Groceries has no subcategories
        result = service.validate_category("Groceries", "SomeSubcat")

        # Assert
        assert not result.is_valid
        assert len(result.errors) == 1
        assert "Subcategory 'SomeSubcat' not found" in result.errors[0]

    def it_should_validate_empty_string_as_no_subcategory(
        self, sample_category_config: CategoryConfig
    ):
        # Arrange
        service = CategorizationService(sample_category_config)

        # Act
        result = service.validate_category("Housing", "")

        # Assert
        assert result.is_valid
        assert len(result.errors) == 0


class DescribeFindMatchingTransactions:
    """Tests for finding matching transactions."""

    def it_should_find_by_exact_description(self, sample_transactions: list[TransactionGroup]):
        # Arrange
        service = CategorizationService(CategoryConfig())
        criteria = SearchCriteria(description="Rent payment")

        # Act
        matches = service.find_matching_transactions(criteria, sample_transactions)

        # Assert
        assert len(matches) == 1
        assert matches[0].primary.description == "Rent payment"

    def it_should_find_by_description_prefix(self, sample_transactions: list[TransactionGroup]):
        # Arrange
        service = CategorizationService(CategoryConfig())
        criteria = SearchCriteria(desc_prefix="SPOTIFY")

        # Act
        matches = service.find_matching_transactions(criteria, sample_transactions)

        # Assert
        assert len(matches) == 2  # Both SPOTIFY transactions
        for match in matches:
            assert match.primary.description.startswith("SPOTIFY")

    def it_should_find_by_regex_pattern(self, sample_transactions: list[TransactionGroup]):
        # Arrange
        service = CategorizationService(CategoryConfig())
        criteria = SearchCriteria(pattern=r".*Payment")

        # Act
        matches = service.find_matching_transactions(criteria, sample_transactions)

        # Assert
        assert len(matches) == 2  # "Rent payment" and "Example Utility Payment"

    def it_should_find_by_description_and_amount(self, sample_transactions: list[TransactionGroup]):
        # Arrange
        service = CategorizationService(CategoryConfig())
        criteria = SearchCriteria(desc_prefix="SPOTIFY", amount=-10.99)

        # Act
        matches = service.find_matching_transactions(criteria, sample_transactions)

        # Assert
        assert len(matches) == 2
        for match in matches:
            assert match.primary.amount == -10.99

    def it_should_return_empty_list_when_no_matches(
        self, sample_transactions: list[TransactionGroup]
    ):
        # Arrange
        service = CategorizationService(CategoryConfig())
        criteria = SearchCriteria(description="NonExistent Transaction")

        # Act
        matches = service.find_matching_transactions(criteria, sample_transactions)

        # Assert
        assert len(matches) == 0

    def it_should_handle_invalid_regex_pattern(self, sample_transactions: list[TransactionGroup]):
        # Arrange
        service = CategorizationService(CategoryConfig())
        criteria = SearchCriteria(pattern="[invalid")

        # Act
        matches = service.find_matching_transactions(criteria, sample_transactions)

        # Assert
        assert len(matches) == 0


class DescribePlanCategorization:
    """Tests for categorization planning."""

    def it_should_create_valid_plan_for_valid_category(
        self,
        sample_category_config: CategoryConfig,
        sample_transactions: list[TransactionGroup],
    ):
        # Arrange
        service = CategorizationService(sample_category_config)
        criteria = SearchCriteria(description="Rent payment")

        # Act
        plan = service.plan_categorization(criteria, sample_transactions, "Housing", "Rent")

        # Assert
        assert plan.is_valid
        assert len(plan.validation_errors) == 0
        assert plan.category == "Housing"
        assert plan.subcategory == "Rent"
        assert len(plan.matches) == 1
        assert plan.matches[0].primary.description == "Rent payment"

    def it_should_create_invalid_plan_for_invalid_category(
        self,
        sample_category_config: CategoryConfig,
        sample_transactions: list[TransactionGroup],
    ):
        # Arrange
        service = CategorizationService(sample_category_config)
        criteria = SearchCriteria(description="Rent payment")

        # Act
        plan = service.plan_categorization(criteria, sample_transactions, "InvalidCat", None)

        # Assert
        assert not plan.is_valid
        assert len(plan.validation_errors) > 0
        assert "not found" in plan.validation_errors[0]
        assert len(plan.matches) == 1  # Still found matches, just invalid category

    def it_should_create_plan_with_no_matches(
        self,
        sample_category_config: CategoryConfig,
        sample_transactions: list[TransactionGroup],
    ):
        # Arrange
        service = CategorizationService(sample_category_config)
        criteria = SearchCriteria(description="Nonexistent")

        # Act
        plan = service.plan_categorization(criteria, sample_transactions, "Housing", None)

        # Assert
        assert plan.is_valid  # Category is valid
        assert len(plan.validation_errors) == 0
        assert len(plan.matches) == 0

    def it_should_support_none_subcategory(
        self,
        sample_category_config: CategoryConfig,
        sample_transactions: list[TransactionGroup],
    ):
        # Arrange
        service = CategorizationService(sample_category_config)
        criteria = SearchCriteria(description="Rent payment")

        # Act
        plan = service.plan_categorization(criteria, sample_transactions, "Housing", None)

        # Assert
        assert plan.is_valid
        assert plan.category == "Housing"
        assert plan.subcategory is None


class DescribeApplyCategorization:
    """Tests for applying categorization."""

    def it_should_apply_category_to_single_transaction(
        self, sample_transactions: list[TransactionGroup]
    ):
        # Arrange
        service = CategorizationService(CategoryConfig())
        matches = [sample_transactions[0]]  # First transaction only

        # Act
        result = service.apply_categorization(matches, "Housing", "Rent")

        # Assert
        assert result.count == 1
        assert len(result.errors) == 0
        assert len(result.updated_transactions) == 1
        updated = result.updated_transactions[0]
        assert updated.primary.category == "Housing"
        assert updated.primary.subcategory == "Rent"
        # Original should be unchanged
        assert sample_transactions[0].primary.category is None

    def it_should_apply_category_to_multiple_transactions(
        self, sample_transactions: list[TransactionGroup]
    ):
        # Arrange
        service = CategorizationService(CategoryConfig())
        matches = sample_transactions[:2]  # First two transactions

        # Act
        result = service.apply_categorization(matches, "Housing", None)

        # Assert
        assert result.count == 2
        assert len(result.errors) == 0
        assert len(result.updated_transactions) == 2
        for updated in result.updated_transactions:
            assert updated.primary.category == "Housing"
            assert updated.primary.subcategory is None

    def it_should_overwrite_existing_category(self, sample_transactions: list[TransactionGroup]):
        # Arrange
        service = CategorizationService(CategoryConfig())
        # Transaction 4 already has a category
        matches = [sample_transactions[3]]

        # Act
        result = service.apply_categorization(matches, "Housing", "Utilities")

        # Assert
        assert result.count == 1
        assert len(result.errors) == 0
        updated = result.updated_transactions[0]
        assert updated.primary.category == "Housing"
        assert updated.primary.subcategory == "Utilities"
        # Original category should be replaced
        assert sample_transactions[3].primary.category == "Entertainment"

    def it_should_handle_empty_matches_list(self):
        # Arrange
        service = CategorizationService(CategoryConfig())
        matches: list[TransactionGroup] = []

        # Act
        result = service.apply_categorization(matches, "Housing", "Rent")

        # Assert
        assert result.count == 0
        assert len(result.errors) == 0
        assert len(result.updated_transactions) == 0

    def it_should_preserve_other_transaction_fields(
        self, sample_transactions: list[TransactionGroup]
    ):
        # Arrange
        service = CategorizationService(CategoryConfig())
        original = sample_transactions[2]
        matches = [original]

        # Act
        result = service.apply_categorization(matches, "Housing", "Utilities")

        # Assert
        updated = result.updated_transactions[0]
        # All other fields should remain unchanged
        assert updated.primary.transaction_id == original.primary.transaction_id
        assert updated.primary.date == original.primary.date
        assert updated.primary.description == original.primary.description
        assert updated.primary.amount == original.primary.amount
        assert updated.primary.currency == original.primary.currency
        assert updated.primary.account_id == original.primary.account_id
        assert updated.primary.notes == original.primary.notes

    def it_should_handle_none_subcategory(self, sample_transactions: list[TransactionGroup]):
        # Arrange
        service = CategorizationService(CategoryConfig())
        matches = [sample_transactions[0]]

        # Act
        result = service.apply_categorization(matches, "Groceries", None)

        # Assert
        assert result.count == 1
        updated = result.updated_transactions[0]
        assert updated.primary.category == "Groceries"
        assert updated.primary.subcategory is None

    def it_should_clear_subcategory_when_setting_none(
        self, sample_transactions: list[TransactionGroup]
    ):
        # Arrange
        service = CategorizationService(CategoryConfig())
        # Transaction 4 has Entertainment:Music
        matches = [sample_transactions[3]]

        # Act
        result = service.apply_categorization(matches, "Transportation", None)

        # Assert
        updated = result.updated_transactions[0]
        assert updated.primary.category == "Transportation"
        assert updated.primary.subcategory is None


class DescribeEdgeCases:
    """Tests for edge cases and error handling."""

    def it_should_handle_empty_category_config(self):
        # Arrange
        empty_config = CategoryConfig(categories=[])
        service = CategorizationService(empty_config)

        # Act
        result = service.validate_category("AnyCategory", None)

        # Assert
        assert not result.is_valid
        assert "not found" in result.errors[0]

    def it_should_handle_whitespace_in_category_names(self, sample_category_config: CategoryConfig):
        # Arrange
        service = CategorizationService(sample_category_config)

        # Act
        result = service.validate_category("  Housing  ", " Rent ")

        # Assert - Service should handle whitespace or fail gracefully
        # Current implementation uses exact match, so this will fail
        assert not result.is_valid

    def it_should_handle_case_sensitive_category_names(
        self, sample_category_config: CategoryConfig
    ):
        # Arrange
        service = CategorizationService(sample_category_config)

        # Act
        result = service.validate_category("housing", None)

        # Assert - Category names are case-sensitive
        assert not result.is_valid

    def it_should_preserve_transaction_group_structure(
        self, sample_transactions: list[TransactionGroup]
    ):
        # Arrange
        service = CategorizationService(CategoryConfig())
        original = sample_transactions[0]

        # Act
        result = service.apply_categorization([original], "Housing", "Rent")

        # Assert
        updated = result.updated_transactions[0]
        assert updated.group_id == original.group_id
        assert updated.splits == original.splits


class DescribeCategorizationEventEmission:
    """Tests for event emission when categorizing transactions."""

    def it_should_emit_event_when_event_store_provided(
        self, sample_category_config: CategoryConfig, sample_transactions: list[TransactionGroup]
    ):
        # Arrange
        mock_event_store = Mock(spec=EventStore)
        service = CategorizationService(sample_category_config, event_store=mock_event_store)
        txn = sample_transactions[0]

        # Act
        service.apply_categorization([txn], "Housing", "Rent")

        # Assert
        assert mock_event_store.append_event.call_count == 1
        event = mock_event_store.append_event.call_args[0][0]
        assert isinstance(event, TransactionCategorized)
        assert event.transaction_id == txn.primary.transaction_id
        assert event.category == "Housing"
        assert event.subcategory == "Rent"
        assert event.source == "user"
        assert event.previous_category is None

    def it_should_not_emit_event_when_no_event_store(
        self, sample_category_config: CategoryConfig, sample_transactions: list[TransactionGroup]
    ):
        # Arrange - No event store provided
        service = CategorizationService(sample_category_config)
        txn = sample_transactions[0]

        # Act
        result = service.apply_categorization([txn], "Housing", "Rent")

        # Assert - Should not error, just skip event emission
        assert result.count == 1
        assert len(result.updated_transactions) == 1

    def it_should_track_previous_category_in_event(
        self, sample_category_config: CategoryConfig, sample_transactions: list[TransactionGroup]
    ):
        # Arrange
        mock_event_store = Mock(spec=EventStore)
        service = CategorizationService(sample_category_config, event_store=mock_event_store)
        # Pre-categorized transaction
        txn = sample_transactions[0]
        txn.primary.category = "Transportation"
        txn.primary.subcategory = "Transit"

        # Act - Re-categorize
        service.apply_categorization([txn], "Housing", "Rent")

        # Assert
        event = mock_event_store.append_event.call_args[0][0]
        assert event.previous_category == "Transportation"
        assert event.previous_subcategory == "Transit"
        assert event.category == "Housing"
        assert event.subcategory == "Rent"

    def it_should_emit_event_for_each_transaction(
        self, sample_category_config: CategoryConfig, sample_transactions: list[TransactionGroup]
    ):
        # Arrange
        mock_event_store = Mock(spec=EventStore)
        service = CategorizationService(sample_category_config, event_store=mock_event_store)

        # Act - Categorize 3 transactions
        service.apply_categorization(sample_transactions[:3], "Housing", "Utilities")

        # Assert - Should emit 3 events
        assert mock_event_store.append_event.call_count == 3
        for call in mock_event_store.append_event.call_args_list:
            event = call[0][0]
            assert isinstance(event, TransactionCategorized)
            assert event.category == "Housing"
            assert event.subcategory == "Utilities"

    def it_should_write_events_to_real_event_store(
        self, sample_category_config: CategoryConfig, sample_transactions: list[TransactionGroup]
    ):
        # Arrange
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "events.db"
            event_store = EventStore(str(store_path))

            service = CategorizationService(sample_category_config, event_store=event_store)
            txn = sample_transactions[0]

            # Act
            service.apply_categorization([txn], "Housing", "Rent")

            # Assert - Events should be persisted
            events = event_store.get_events_by_type("TransactionCategorized")
            assert len(events) == 1
            assert events[0].transaction_id == txn.primary.transaction_id
            assert events[0].category == "Housing"
            assert events[0].subcategory == "Rent"
