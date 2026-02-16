"""Tests for training data builder that extracts pairs from events."""

from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from finance.ml.training_data_builder import TrainingDataBuilder
from finance.model.duplicate import TransactionPair
from finance.model.events import DuplicateConfirmed, DuplicateRejected, DuplicateSuggested
from finance.storage.event_store import EventStore


@pytest.fixture
def temp_event_store():
    """Create a temporary event store for testing."""
    with TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "test_events.db"
        yield EventStore(str(store_path))


@pytest.fixture
def sample_pair():
    """Create a sample transaction pair for testing."""
    return TransactionPair(
        txn1_id="abc123",
        txn1_date=date(2025, 11, 15),
        txn1_description="SPOTIFY PREMIUM",
        txn1_amount=-10.99,
        txn1_account="MYBANK_CHQ",
        txn2_id="def456",
        txn2_date=date(2025, 11, 15),
        txn2_description="SPOTIFY PREMIUM ON",
        txn2_amount=-10.99,
        txn2_account="MYBANK_CHQ",
    )


class DescribeTrainingDataBuilder:
    """Tests for TrainingDataBuilder."""

    def it_should_extract_pairs_from_confirmed_events(self, temp_event_store, sample_pair):
        """Should extract transaction pairs from DuplicateConfirmed events."""
        # Create a suggestion event with pair data
        suggestion = DuplicateSuggested(
            transaction_id_1=sample_pair.txn1_id,
            transaction_id_2=sample_pair.txn2_id,
            confidence=0.95,
            reasoning="Same transaction",
            model="qwen3:30b",
            prompt_version="v1",
            assessment={
                "is_duplicate": True,
                "confidence": 0.95,
                "reasoning": "Same transaction",
                "pair": sample_pair.model_dump(),
            },
        )
        temp_event_store.append_event(suggestion)

        # Create a confirmed event
        confirmed = DuplicateConfirmed(
            suggestion_event_id=suggestion.event_id,
            primary_transaction_id=sample_pair.txn1_id,
            duplicate_transaction_id=sample_pair.txn2_id,
            canonical_description="SPOTIFY PREMIUM",
            llm_was_correct=True,
        )
        temp_event_store.append_event(confirmed)

        # Extract training data
        builder = TrainingDataBuilder(temp_event_store)
        pairs, labels = builder.load_from_events()

        # Should have one training example
        assert len(pairs) == 1
        assert len(labels) == 1
        assert labels[0] is True  # Confirmed = positive example

        # Verify pair data is correct
        pair = pairs[0]
        assert pair.txn1_id == sample_pair.txn1_id
        assert pair.txn2_id == sample_pair.txn2_id
        assert pair.txn1_description == sample_pair.txn1_description
        assert pair.txn2_description == sample_pair.txn2_description

    def it_should_extract_pairs_from_rejected_events(self, temp_event_store, sample_pair):
        """Should extract transaction pairs from DuplicateRejected events."""
        # Create a suggestion event with pair data
        suggestion = DuplicateSuggested(
            transaction_id_1=sample_pair.txn1_id,
            transaction_id_2=sample_pair.txn2_id,
            confidence=0.85,
            reasoning="Might be same",
            model="qwen3:30b",
            prompt_version="v1",
            assessment={
                "is_duplicate": True,
                "confidence": 0.85,
                "reasoning": "Might be same",
                "pair": sample_pair.model_dump(),
            },
        )
        temp_event_store.append_event(suggestion)

        # Create a rejected event
        rejected = DuplicateRejected(
            suggestion_event_id=suggestion.event_id,
            transaction_id_1=sample_pair.txn1_id,
            transaction_id_2=sample_pair.txn2_id,
            user_rationale="Different merchants",
            llm_was_correct=False,
        )
        temp_event_store.append_event(rejected)

        # Extract training data
        builder = TrainingDataBuilder(temp_event_store)
        pairs, labels = builder.load_from_events()

        # Should have one training example
        assert len(pairs) == 1
        assert len(labels) == 1
        assert labels[0] is False  # Rejected = negative example

    def it_should_handle_multiple_feedback_events(self, temp_event_store, sample_pair):
        """Should extract multiple training examples from multiple events."""
        # Create two suggestion events
        suggestion1 = DuplicateSuggested(
            transaction_id_1=sample_pair.txn1_id,
            transaction_id_2=sample_pair.txn2_id,
            confidence=0.95,
            reasoning="Same",
            model="qwen3:30b",
            prompt_version="v1",
            assessment={
                "is_duplicate": True,
                "confidence": 0.95,
                "reasoning": "Same",
                "pair": sample_pair.model_dump(),
            },
        )
        temp_event_store.append_event(suggestion1)

        # Different pair for second suggestion
        different_pair = TransactionPair(
            txn1_id="ghi789",
            txn1_date=date(2025, 11, 16),
            txn1_description="STARBUCKS #1234",
            txn1_amount=-5.50,
            txn1_account="MYBANK_CHQ",
            txn2_id="jkl012",
            txn2_date=date(2025, 11, 16),
            txn2_description="STARBUCKS #5678",
            txn2_amount=-5.50,
            txn2_account="MYBANK_CHQ",
        )

        suggestion2 = DuplicateSuggested(
            transaction_id_1=different_pair.txn1_id,
            transaction_id_2=different_pair.txn2_id,
            confidence=0.70,
            reasoning="Maybe same",
            model="qwen3:30b",
            prompt_version="v1",
            assessment={
                "is_duplicate": True,
                "confidence": 0.70,
                "reasoning": "Maybe same",
                "pair": different_pair.model_dump(),
            },
        )
        temp_event_store.append_event(suggestion2)

        # One confirmed, one rejected
        confirmed = DuplicateConfirmed(
            suggestion_event_id=suggestion1.event_id,
            primary_transaction_id=sample_pair.txn1_id,
            duplicate_transaction_id=sample_pair.txn2_id,
            canonical_description="SPOTIFY PREMIUM",
            llm_was_correct=True,
        )
        temp_event_store.append_event(confirmed)

        rejected = DuplicateRejected(
            suggestion_event_id=suggestion2.event_id,
            transaction_id_1=different_pair.txn1_id,
            transaction_id_2=different_pair.txn2_id,
            user_rationale="Different locations",
            llm_was_correct=False,
        )
        temp_event_store.append_event(rejected)

        # Extract training data
        builder = TrainingDataBuilder(temp_event_store)
        pairs, labels = builder.load_from_events()

        # Should have two training examples
        assert len(pairs) == 2
        assert len(labels) == 2
        assert labels[0] is True  # First was confirmed
        assert labels[1] is False  # Second was rejected

    def it_should_handle_missing_suggestion_events_gracefully(self, temp_event_store, sample_pair):
        """Should skip feedback events when suggestion event is missing."""
        # Create confirmed event without a corresponding suggestion
        confirmed = DuplicateConfirmed(
            suggestion_event_id="nonexistent-id",
            primary_transaction_id=sample_pair.txn1_id,
            duplicate_transaction_id=sample_pair.txn2_id,
            canonical_description="SPOTIFY PREMIUM",
            llm_was_correct=True,
        )
        temp_event_store.append_event(confirmed)

        # Extract training data - should handle gracefully
        builder = TrainingDataBuilder(temp_event_store)
        pairs, labels = builder.load_from_events()

        # Should have zero training examples (missing suggestion)
        assert len(pairs) == 0
        assert len(labels) == 0

    def it_should_calculate_statistics(self, temp_event_store, sample_pair):
        """Should calculate training data statistics."""
        # Create multiple suggestion and feedback events
        for i in range(3):
            suggestion = DuplicateSuggested(
                transaction_id_1=f"txn{i}a",
                transaction_id_2=f"txn{i}b",
                confidence=0.90,
                reasoning="Test",
                model="qwen3:30b",
                prompt_version="v1",
                assessment={
                    "is_duplicate": True,
                    "confidence": 0.90,
                    "reasoning": "Test",
                    "pair": {
                        "txn1_id": f"txn{i}a",
                        "txn1_date": "2025-11-15",
                        "txn1_description": "TEST",
                        "txn1_amount": -10.0,
                        "txn1_account": "MYBANK_CHQ",
                        "txn1_source_file": None,
                        "txn2_id": f"txn{i}b",
                        "txn2_date": "2025-11-15",
                        "txn2_description": "TEST",
                        "txn2_amount": -10.0,
                        "txn2_account": "MYBANK_CHQ",
                        "txn2_source_file": None,
                    },
                },
            )
            temp_event_store.append_event(suggestion)

            # First two confirmed, last one rejected
            if i < 2:
                confirmed = DuplicateConfirmed(
                    suggestion_event_id=suggestion.event_id,
                    primary_transaction_id=f"txn{i}a",
                    duplicate_transaction_id=f"txn{i}b",
                    canonical_description="TEST",
                    llm_was_correct=True,
                )
                temp_event_store.append_event(confirmed)
            else:
                rejected = DuplicateRejected(
                    suggestion_event_id=suggestion.event_id,
                    transaction_id_1=f"txn{i}a",
                    transaction_id_2=f"txn{i}b",
                    llm_was_correct=False,
                )
                temp_event_store.append_event(rejected)

        # Get statistics
        builder = TrainingDataBuilder(temp_event_store)
        stats = builder.get_statistics()

        assert stats["total_examples"] == 3
        assert stats["positive_examples"] == 2
        assert stats["negative_examples"] == 1
        assert stats["class_balance"] == pytest.approx(2 / 3)
        assert stats["sufficient_for_training"] is False  # Need 10+

    def it_should_return_empty_when_no_events(self, temp_event_store):
        """Should return empty lists when no feedback events exist."""
        builder = TrainingDataBuilder(temp_event_store)
        pairs, labels = builder.load_from_events()

        assert len(pairs) == 0
        assert len(labels) == 0

        stats = builder.get_statistics()
        assert stats["total_examples"] == 0
        assert stats["sufficient_for_training"] is False
