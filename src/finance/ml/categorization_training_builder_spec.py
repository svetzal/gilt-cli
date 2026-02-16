"""Tests for categorization training data builder."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import numpy as np

from finance.ml.categorization_training_builder import CategorizationTrainingBuilder
from finance.model.events import TransactionCategorized, TransactionImported
from finance.storage.event_store import EventStore


@pytest.fixture
def temp_event_store():
    """Create temporary event store for testing."""
    with TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "events.db"
        yield EventStore(str(store_path))


class DescribeCategorizationTrainingBuilder:
    """Tests for building training data from categorization events."""

    def it_should_extract_user_categorizations(self, temp_event_store):
        """Should load transactions and categories from user events."""
        # Add TransactionImported events
        txn1_imported = TransactionImported(
            transaction_id="txn1",
            transaction_date="2025-01-15",
            source_file="test.csv",
            source_account="CHQ",
            raw_description="SPOTIFY MUSIC",
            amount=Decimal("-12.99"),
            currency="CAD",
            raw_data={},
        )
        temp_event_store.append_event(txn1_imported)

        txn2_imported = TransactionImported(
            transaction_id="txn2",
            transaction_date="2025-01-16",
            source_file="test.csv",
            source_account="CHQ",
            raw_description="LOBLAWS GROCERY",
            amount=Decimal("-45.67"),
            currency="CAD",
            raw_data={},
        )
        temp_event_store.append_event(txn2_imported)

        # Add TransactionCategorized events (user source)
        cat1 = TransactionCategorized(
            transaction_id="txn1",
            category="Entertainment",
            subcategory="Music",
            source="user",
            previous_category=None,
        )
        temp_event_store.append_event(cat1)

        cat2 = TransactionCategorized(
            transaction_id="txn2",
            category="Groceries",
            subcategory=None,
            source="user",
            previous_category=None,
        )
        temp_event_store.append_event(cat2)

        # Load training data
        builder = CategorizationTrainingBuilder(temp_event_store)
        transaction_data, category_labels = builder.load_from_events(source_filter="user")

        assert len(transaction_data) == 2
        assert len(category_labels) == 2

        # Check first transaction
        assert transaction_data[0]["transaction_id"] == "txn1"
        assert transaction_data[0]["description"] == "SPOTIFY MUSIC"
        assert transaction_data[0]["amount"] == -12.99
        assert category_labels[0] == "Entertainment:Music"

        # Check second transaction
        assert transaction_data[1]["transaction_id"] == "txn2"
        assert transaction_data[1]["description"] == "LOBLAWS GROCERY"
        assert category_labels[1] == "Groceries"

    def it_should_filter_by_source(self, temp_event_store):
        """Should only include categorizations from specified source."""
        # Add transaction
        txn_imported = TransactionImported(
            transaction_id="txn1",
            transaction_date="2025-01-15",
            source_file="test.csv",
            source_account="CHQ",
            raw_description="SPOTIFY MUSIC",
            amount=Decimal("-12.99"),
            currency="CAD",
            raw_data={},
        )
        temp_event_store.append_event(txn_imported)

        # Add user categorization
        user_cat = TransactionCategorized(
            transaction_id="txn1",
            category="Entertainment",
            subcategory="Music",
            source="user",
        )
        temp_event_store.append_event(user_cat)

        # Add LLM categorization (different category)
        llm_cat = TransactionCategorized(
            transaction_id="txn1",
            category="Subscriptions",
            subcategory=None,
            source="llm",
            previous_category="Entertainment",
            previous_subcategory="Music",
        )
        temp_event_store.append_event(llm_cat)

        # Load only user categorizations
        builder = CategorizationTrainingBuilder(temp_event_store)
        transaction_data, category_labels = builder.load_from_events(source_filter="user")

        assert len(transaction_data) == 1
        assert category_labels[0] == "Entertainment:Music"

    def it_should_build_feature_vectors(self, temp_event_store):
        """Should extract TF-IDF and numeric features."""
        # Add transactions
        txn1 = TransactionImported(
            transaction_id="txn1",
            transaction_date="2025-01-15",
            source_file="test.csv",
            source_account="CHQ",
            raw_description="SPOTIFY PREMIUM",
            amount=Decimal("-12.99"),
            currency="CAD",
            raw_data={},
        )
        temp_event_store.append_event(txn1)

        txn2 = TransactionImported(
            transaction_id="txn2",
            transaction_date="2025-01-16",
            source_file="test.csv",
            source_account="CHQ",
            raw_description="LOBLAWS GROCERY STORE",
            amount=Decimal("-45.67"),
            currency="CAD",
            raw_data={},
        )
        temp_event_store.append_event(txn2)

        # Add categorizations
        cat1 = TransactionCategorized(
            transaction_id="txn1",
            category="Entertainment",
            subcategory="Music",
            source="user",
        )
        temp_event_store.append_event(cat1)

        cat2 = TransactionCategorized(
            transaction_id="txn2",
            category="Groceries",
            source="user",
        )
        temp_event_store.append_event(cat2)

        # Build features
        builder = CategorizationTrainingBuilder(temp_event_store)
        transaction_data, _ = builder.load_from_events()
        features = builder.build_features(transaction_data)

        assert features.shape[0] == 2  # Two transactions
        assert features.shape[1] > 1  # TF-IDF features + amount

    def it_should_get_complete_training_dataset(self, temp_event_store):
        """Should return features, labels, and category names."""
        # Add multiple transactions in same category
        for i in range(3):
            txn = TransactionImported(
                transaction_id=f"txn{i}",
                transaction_date="2025-01-15",
                source_file="test.csv",
                source_account="CHQ",
                raw_description=f"SPOTIFY PAYMENT {i}",
                amount=Decimal("-12.99"),
                currency="CAD",
                raw_data={},
            )
            temp_event_store.append_event(txn)

            cat = TransactionCategorized(
                transaction_id=f"txn{i}",
                category="Entertainment",
                subcategory="Music",
                source="user",
            )
            temp_event_store.append_event(cat)

        # Get training data
        builder = CategorizationTrainingBuilder(temp_event_store)
        features, labels, category_names = builder.get_training_data(
            min_samples_per_category=2
        )

        assert features.shape[0] == 3  # All 3 transactions
        assert len(labels) == 3
        assert len(category_names) == 1
        assert category_names[0] == "Entertainment:Music"
        assert np.all(labels == 0)  # All have same label (index 0)

    def it_should_filter_categories_with_few_samples(self, temp_event_store):
        """Should exclude categories with fewer than min_samples."""
        # Add 1 transaction for Entertainment (will be filtered)
        txn1 = TransactionImported(
            transaction_id="txn1",
            transaction_date="2025-01-15",
            source_file="test.csv",
            source_account="CHQ",
            raw_description="SPOTIFY",
            amount=Decimal("-12.99"),
            currency="CAD",
            raw_data={},
        )
        temp_event_store.append_event(txn1)

        cat1 = TransactionCategorized(
            transaction_id="txn1",
            category="Entertainment",
            source="user",
        )
        temp_event_store.append_event(cat1)

        # Add 3 transactions for Groceries (will be kept)
        for i in range(3):
            txn = TransactionImported(
                transaction_id=f"grocery{i}",
                transaction_date="2025-01-15",
                source_file="test.csv",
                source_account="CHQ",
                raw_description=f"LOBLAWS {i}",
                amount=Decimal("-30.00"),
                currency="CAD",
                raw_data={},
            )
            temp_event_store.append_event(txn)

            cat = TransactionCategorized(
                transaction_id=f"grocery{i}",
                category="Groceries",
                source="user",
            )
            temp_event_store.append_event(cat)

        # Get training data with min_samples=2
        builder = CategorizationTrainingBuilder(temp_event_store)
        features, labels, category_names = builder.get_training_data(
            min_samples_per_category=2
        )

        # Should only have Groceries (3 samples >= 2)
        assert len(category_names) == 1
        assert category_names[0] == "Groceries"
        assert features.shape[0] == 3
        assert len(labels) == 3
