"""Tests for transaction categorization classifier."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from gilt.ml.categorization_classifier import CategorizationClassifier
from gilt.model.events import TransactionCategorized, TransactionImported
from gilt.storage.event_store import EventStore


@pytest.fixture
def event_store_with_training_data():
    """Create event store with sufficient training data."""
    with TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "events.db"
        store = EventStore(str(store_path))

        # Create training data for two categories
        # Category 1: Entertainment (Spotify/Netflix patterns)
        entertainment_patterns = [
            "SPOTIFY PREMIUM",
            "SPOTIFY MUSIC",
            "SPOTIFY MONTHLY",
            "NETFLIX STREAMING",
            "NETFLIX SUBSCRIPTION",
            "NETFLIX MONTHLY",
        ]

        for i, desc in enumerate(entertainment_patterns):
            txn = TransactionImported(
                transaction_id=f"ent{i}",
                transaction_date="2025-01-15",
                source_file="test.csv",
                source_account="MC",
                raw_description=desc,
                amount=Decimal("-12.99"),
                currency="CAD",
                raw_data={},
            )
            store.append_event(txn)

            cat = TransactionCategorized(
                transaction_id=f"ent{i}",
                category="Entertainment",
                subcategory="Streaming",
                source="user",
            )
            store.append_event(cat)

        # Category 2: Groceries (Loblaws/Sobeys patterns)
        grocery_patterns = [
            "LOBLAWS STORE #123",
            "LOBLAWS GROCERY",
            "LOBLAWS SUPERMARKET",
            "SOBEYS GROCERY",
            "SOBEYS STORE",
            "SOBEYS SUPERMARKET",
        ]

        for i, desc in enumerate(grocery_patterns):
            txn = TransactionImported(
                transaction_id=f"groc{i}",
                transaction_date="2025-01-16",
                source_file="test.csv",
                source_account="CHQ",
                raw_description=desc,
                amount=Decimal("-45.67"),
                currency="CAD",
                raw_data={},
            )
            store.append_event(txn)

            cat = TransactionCategorized(
                transaction_id=f"groc{i}",
                category="Groceries",
                source="user",
            )
            store.append_event(cat)

        yield store


class DescribeCategorizationClassifier:
    """Tests for ML-based transaction categorization."""

    def it_should_train_from_user_categorizations(self, event_store_with_training_data):
        """Should successfully train classifier from events."""
        # Arrange
        classifier = CategorizationClassifier(
            event_store_with_training_data,
            min_samples_per_category=3,
        )

        # Act
        metrics = classifier.train()

        # Assert
        assert classifier.is_trained
        assert metrics["num_categories"] == 2
        assert metrics["total_samples"] == 12
        assert metrics["train_accuracy"] > 0.5  # Should learn something
        assert "Entertainment:Streaming" in metrics["categories"]
        assert "Groceries" in metrics["categories"]

    def it_should_require_minimum_samples_per_category(self, event_store_with_training_data):
        """Should filter out categories with too few samples."""
        # Arrange
        classifier = CategorizationClassifier(
            event_store_with_training_data,
            min_samples_per_category=10,  # More than available per category
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Insufficient training data"):
            classifier.train()

    def it_should_predict_entertainment_transactions(self, event_store_with_training_data):
        """Should correctly classify streaming service transactions."""
        # Arrange
        classifier = CategorizationClassifier(event_store_with_training_data)
        classifier.train()

        # Act - Predict on new Spotify transaction
        category, confidence = classifier.predict_single(
            description="SPOTIFY SUBSCRIPTION",
            amount=-12.99,
            account="MC",
            confidence_threshold=0.5,
        )

        # Assert
        assert category is not None
        assert "Entertainment" in category
        assert confidence >= 0.5

    def it_should_predict_grocery_transactions(self, event_store_with_training_data):
        """Should correctly classify grocery store transactions."""
        # Arrange
        classifier = CategorizationClassifier(event_store_with_training_data)
        classifier.train()

        # Act - Predict on new Loblaws transaction
        category, confidence = classifier.predict_single(
            description="LOBLAWS PAYMENT",
            amount=-50.00,
            account="CHQ",
            confidence_threshold=0.5,
        )

        # Assert
        assert category is not None
        assert "Groceries" in category
        assert confidence >= 0.5

    def it_should_return_none_below_confidence_threshold(self, event_store_with_training_data):
        """Should not predict when confidence is too low."""
        # Arrange
        classifier = CategorizationClassifier(event_store_with_training_data)
        classifier.train()

        # Act - Predict on ambiguous transaction with high threshold
        category, confidence = classifier.predict_single(
            description="SOME RANDOM PAYMENT",
            amount=-25.00,
            account="CHQ",
            confidence_threshold=0.9,  # Very high threshold
        )

        # Assert - Should return None due to low confidence
        assert category is None or confidence < 0.9

    def it_should_predict_batch_of_transactions(self, event_store_with_training_data):
        """Should predict categories for multiple transactions at once."""
        # Arrange
        classifier = CategorizationClassifier(event_store_with_training_data)
        classifier.train()

        transactions = [
            {
                "description": "SPOTIFY FAMILY PLAN",
                "amount": -15.99,
                "account": "MC",
                "date": "2025-02-01",
                "transaction_id": "test1",
            },
            {
                "description": "LOBLAWS WEEKLY SHOP",
                "amount": -65.00,
                "account": "CHQ",
                "date": "2025-02-01",
                "transaction_id": "test2",
            },
        ]

        # Act
        predictions = classifier.predict(transactions, confidence_threshold=0.5)

        # Assert
        assert len(predictions) == 2
        # First should be Entertainment
        assert predictions[0][0] is not None
        assert "Entertainment" in predictions[0][0]
        # Second should be Groceries
        assert predictions[1][0] is not None
        assert "Groceries" in predictions[1][0]

    def it_should_provide_feature_importance(self, event_store_with_training_data):
        """Should identify most important features for classification."""
        # Arrange
        classifier = CategorizationClassifier(event_store_with_training_data)
        classifier.train()

        # Act
        important_features = classifier.get_feature_importance(top_n=10)

        # Assert
        assert len(important_features) > 0
        assert len(important_features) <= 10
        # Each feature is (name, importance)
        for name, importance in important_features:
            assert isinstance(name, str)
            assert 0.0 <= importance <= 1.0
        # Should be sorted by importance
        importances = [imp for _, imp in important_features]
        assert importances == sorted(importances, reverse=True)

    def it_should_raise_error_when_predicting_before_training(self, event_store_with_training_data):
        """Should not allow prediction before training."""
        # Arrange
        classifier = CategorizationClassifier(event_store_with_training_data)

        # Act & Assert
        with pytest.raises(ValueError, match="not trained"):
            classifier.predict_single("TEST", -10.0, "CHQ")
