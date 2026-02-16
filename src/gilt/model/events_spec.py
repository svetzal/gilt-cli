"""
Tests for event sourcing models.
"""

from datetime import datetime
from decimal import Decimal
import json

import pytest
from pydantic import ValidationError

from gilt.model.events import (
    Event,
    TransactionImported,
    TransactionDescriptionObserved,
    DuplicateSuggested,
    DuplicateConfirmed,
    DuplicateRejected,
    TransactionCategorized,
    CategorizationRuleCreated,
    BudgetCreated,
    PromptUpdated,
)


class DescribeEvent:
    """Test base Event functionality."""

    def it_should_generate_event_id_and_timestamp(self):
        """Base events should auto-generate ID and timestamp."""
        event = Event(event_type="TestEvent")
        assert event.event_id is not None
        assert event.event_timestamp is not None
        assert isinstance(event.event_timestamp, datetime)

    def it_should_serialize_to_json(self):
        """Events should serialize to JSON."""
        event = Event(event_type="TestEvent", aggregate_type="test", aggregate_id="test-123")
        json_str = event.model_dump_json()
        data = json.loads(json_str)
        assert data["event_type"] == "TestEvent"
        assert data["aggregate_type"] == "test"
        assert data["aggregate_id"] == "test-123"

    def it_should_deserialize_from_json(self):
        """Events should deserialize from JSON."""
        event = Event(event_type="TestEvent")
        json_str = event.model_dump_json()
        restored = Event.model_validate_json(json_str)
        assert restored.event_type == event.event_type
        assert restored.event_id == event.event_id


class DescribeTransactionImported:
    """Test TransactionImported event."""

    def it_should_create_valid_transaction_imported_event(self):
        """Should create a valid TransactionImported event."""
        event = TransactionImported(
            transaction_date="2025-10-15",
            transaction_id="abc123",
            source_file="2025-11-16-mybank-chequing.csv",
            source_account="MYBANK_CHQ",
            raw_description="TRANSIT FARE/REF1234ABCD Exampleville",
            amount=Decimal("-10.31"),
            currency="CAD",
            raw_data={"date": "10/15/2025", "description": "PRESTO FARE", "amount": "-10.31"},
        )
        assert event.event_type == "TransactionImported"
        assert event.transaction_id == "abc123"
        assert event.amount == Decimal("-10.31")
        assert event.aggregate_type == "transaction"
        assert event.aggregate_id == "abc123"

    def it_should_require_mandatory_fields(self):
        """Should validate mandatory fields."""
        with pytest.raises(ValidationError):
            TransactionImported()

    def it_should_serialize_and_deserialize(self):
        """Should serialize to JSON and deserialize back."""
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
        json_str = event.model_dump_json()
        restored = TransactionImported.model_validate_json(json_str)
        assert restored.transaction_id == event.transaction_id
        assert restored.amount == event.amount


class DescribeTransactionDescriptionObserved:
    """Test TransactionDescriptionObserved event."""

    def it_should_create_valid_description_observed_event(self):
        """Should create a valid description change event."""
        event = TransactionDescriptionObserved(
            original_transaction_id="hash-1",
            new_transaction_id="hash-2",
            transaction_date="2025-10-15",
            original_description="TRANSIT FARE Exampleville",
            new_description="TRANSIT FARE Exampleville ON",
            source_file="2025-11-17-mybank-chequing.csv",
            source_account="MYBANK_CHQ",
            amount=Decimal("-10.31"),
        )
        assert event.event_type == "TransactionDescriptionObserved"
        assert event.original_transaction_id == "hash-1"
        assert event.new_transaction_id == "hash-2"


class DescribeDuplicateSuggested:
    """Test DuplicateSuggested event."""

    def it_should_create_valid_duplicate_suggested_event(self):
        """Should create a valid duplicate suggestion."""
        event = DuplicateSuggested(
            transaction_id_1="hash-1",
            transaction_id_2="hash-2",
            confidence=0.92,
            reasoning="Same date, amount, account",
            model="qwen2.5:3b",
            prompt_version="v2",
            assessment={
                "is_duplicate": True,
                "same_date": True,
                "same_amount": True,
                "same_account": True,
                "description_similarity": 0.95,
            },
        )
        assert event.event_type == "DuplicateSuggested"
        assert event.confidence == 0.92
        assert event.assessment["is_duplicate"] is True

    def it_should_validate_confidence_range(self):
        """Confidence should be between 0 and 1."""
        with pytest.raises(ValidationError):
            DuplicateSuggested(
                transaction_id_1="h1",
                transaction_id_2="h2",
                confidence=1.5,
                reasoning="test",
                model="test",
                prompt_version="v1",
                assessment={},
            )


class DescribeDuplicateConfirmed:
    """Test DuplicateConfirmed event."""

    def it_should_create_valid_duplicate_confirmed_event(self):
        """Should create a valid duplicate confirmation."""
        event = DuplicateConfirmed(
            suggestion_event_id="suggestion-uuid",
            primary_transaction_id="hash-1",
            duplicate_transaction_id="hash-2",
            canonical_description="TRANSIT FARE Exampleville ON",
            user_rationale="Prefer format with province",
            llm_was_correct=True,
        )
        assert event.event_type == "DuplicateConfirmed"
        assert event.llm_was_correct is True
        assert event.canonical_description == "TRANSIT FARE Exampleville ON"


class DescribeDuplicateRejected:
    """Test DuplicateRejected event."""

    def it_should_create_valid_duplicate_rejected_event(self):
        """Should create a valid duplicate rejection."""
        event = DuplicateRejected(
            suggestion_event_id="suggestion-uuid",
            transaction_id_1="hash-1",
            transaction_id_2="hash-2",
            user_rationale="Different cities",
            llm_was_correct=False,
        )
        assert event.event_type == "DuplicateRejected"
        assert event.llm_was_correct is False


class DescribeTransactionCategorized:
    """Test TransactionCategorized event."""

    def it_should_create_valid_categorization_event(self):
        """Should create a valid categorization event."""
        event = TransactionCategorized(
            transaction_id="hash-1",
            category="Transportation",
            subcategory="Public Transit",
            source="user",
            confidence=0.95,
            previous_category="Uncategorized",
            rationale="PRESTO is transit",
        )
        assert event.event_type == "TransactionCategorized"
        assert event.category == "Transportation"
        assert event.source == "user"

    def it_should_validate_source_enum(self):
        """Source must be valid enum value."""
        with pytest.raises(ValidationError):
            TransactionCategorized(transaction_id="h1", category="Test", source="invalid_source")


class DescribeCategorizationRuleCreated:
    """Test CategorizationRuleCreated event."""

    def it_should_create_valid_rule_created_event(self):
        """Should create a valid rule creation event."""
        event = CategorizationRuleCreated(
            rule_id="rule-uuid",
            rule_type="description_pattern",
            pattern="PRESTO FARE/.*",
            category="Transportation",
            subcategory="Public Transit",
            enabled=True,
        )
        assert event.event_type == "CategorizationRuleCreated"
        assert event.pattern == "PRESTO FARE/.*"
        assert event.enabled is True


class DescribeBudgetCreated:
    """Test BudgetCreated event."""

    def it_should_create_valid_budget_created_event(self):
        """Should create a valid budget creation event."""
        event = BudgetCreated(
            budget_id="budget-uuid",
            category="Transportation",
            subcategory="Public Transit",
            period_type="monthly",
            start_date="2025-11-01",
            amount=Decimal("200.00"),
            currency="CAD",
        )
        assert event.event_type == "BudgetCreated"
        assert event.amount == Decimal("200.00")
        assert event.period_type == "monthly"


class DescribePromptUpdated:
    """Test PromptUpdated event."""

    def it_should_create_valid_prompt_updated_event(self):
        """Should create a valid prompt update event."""
        event = PromptUpdated(
            prompt_version="v3",
            previous_version="v2",
            learned_patterns=[
                "Transit transactions with different cities are separate trips",
                "Adding 'ON' suffix is common bank formatting",
            ],
            accuracy_metrics={
                "true_positives": 42,
                "false_positives": 3,
                "true_negatives": 15,
                "false_negatives": 2,
                "accuracy": 0.92,
            },
        )
        assert event.event_type == "PromptUpdated"
        assert event.prompt_version == "v3"
        assert len(event.learned_patterns) == 2
        assert event.accuracy_metrics["accuracy"] == 0.92
