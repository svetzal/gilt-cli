"""Transaction categorization classifier using ML.

Trains a classifier from user categorization events to automatically
categorize new transactions based on their descriptions and amounts.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from gilt.ml.categorization_training_builder import CategorizationTrainingBuilder
from gilt.storage.event_store import EventStore


class CategorizationClassifier:
    """ML classifier for automatic transaction categorization.

    Uses RandomForest to predict categories based on:
    - Transaction description (TF-IDF features)
    - Transaction amount (normalized)

    Training data comes from user categorization events in the event store.
    """

    def __init__(
        self,
        event_store: EventStore,
        min_samples_per_category: int = 5,
        test_size: float = 0.2,
        random_state: int = 42,
    ):
        """Initialize classifier with event store.

        Args:
            event_store: Event store containing categorization events
            min_samples_per_category: Minimum samples needed to train on a category
            test_size: Fraction of data to use for testing
            random_state: Random seed for reproducibility
        """
        self.event_store = event_store
        self.min_samples_per_category = min_samples_per_category
        self.test_size = test_size
        self.random_state = random_state

        self.training_builder = CategorizationTrainingBuilder(event_store)
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=random_state,
            class_weight="balanced",  # Handle imbalanced categories
        )

        self.category_names: list[str] = []
        self.is_trained = False
        self.training_metrics: dict = {}

    def train(self) -> dict:
        """Train classifier from user categorization events.

        Returns:
            Training metrics including accuracy, category counts, etc.
        """
        # Load training data
        features, labels, category_names = self.training_builder.get_training_data(
            source_filter="user",
            min_samples_per_category=self.min_samples_per_category,
        )

        if len(features) == 0:
            raise ValueError(
                f"Insufficient training data. Need at least {self.min_samples_per_category} "
                f"samples per category."
            )

        self.category_names = category_names

        # Split into train/test
        X_train, X_test, y_train, y_test = train_test_split(
            features,
            labels,
            test_size=self.test_size,
            random_state=self.random_state,
            stratify=labels,
        )

        # Train classifier
        self.classifier.fit(X_train, y_train)
        self.is_trained = True

        # Evaluate on test set
        train_score = self.classifier.score(X_train, y_train)
        test_score = self.classifier.score(X_test, y_test)

        # Store metrics
        self.training_metrics = {
            "total_samples": len(features),
            "num_categories": len(category_names),
            "train_accuracy": float(train_score),
            "test_accuracy": float(test_score),
            "train_size": len(X_train),
            "test_size": len(X_test),
            "categories": category_names,
        }

        return self.training_metrics

    def predict(
        self,
        transaction_data: list[dict],
        confidence_threshold: float = 0.6,
    ) -> list[tuple[str | None, float]]:
        """Predict categories for transactions.

        Args:
            transaction_data: List of transaction dicts with description, amount, etc.
            confidence_threshold: Minimum confidence to return prediction (0.0-1.0)

        Returns:
            List of (category, confidence) tuples. Category is None if confidence
            is below threshold.
        """
        if not self.is_trained:
            raise ValueError("Classifier not trained. Call train() first.")

        if not transaction_data:
            return []

        # Build features
        features = self.training_builder.build_features(transaction_data)

        # Get predictions with probabilities
        predictions = self.classifier.predict(features)
        probabilities = self.classifier.predict_proba(features)

        # Convert to category names with confidence filtering
        results = []
        for pred_idx, probs in zip(predictions, probabilities, strict=False):
            confidence = float(np.max(probs))

            category = self.category_names[pred_idx] if confidence >= confidence_threshold else None

            results.append((category, confidence))

        return results

    def predict_single(
        self,
        description: str,
        amount: float,
        account: str,
        confidence_threshold: float = 0.6,
    ) -> tuple[str | None, float]:
        """Predict category for a single transaction.

        Args:
            description: Transaction description
            amount: Transaction amount
            account: Account ID
            confidence_threshold: Minimum confidence to return prediction

        Returns:
            Tuple of (category, confidence). Category is None if below threshold.
        """
        transaction_data = [
            {
                "description": description,
                "amount": amount,
                "account": account,
                "date": "2025-01-01",  # Not used in features currently
                "transaction_id": "temp",
            }
        ]

        results = self.predict(transaction_data, confidence_threshold)
        return results[0] if results else (None, 0.0)

    def get_feature_importance(self, top_n: int = 20) -> list[tuple[str, float]]:
        """Get most important features for classification.

        Args:
            top_n: Number of top features to return

        Returns:
            List of (feature_name, importance) tuples sorted by importance
        """
        if not self.is_trained:
            raise ValueError("Classifier not trained. Call train() first.")

        # Get feature names from vectorizer
        feature_names = self.training_builder.vectorizer.get_feature_names_out()
        feature_names = list(feature_names) + ["amount"]  # Add numeric feature

        # Get importances
        importances = self.classifier.feature_importances_

        # Sort by importance
        indices = np.argsort(importances)[::-1][:top_n]

        top_features = [(feature_names[i], float(importances[i])) for i in indices]

        return top_features


__all__ = [
    "CategorizationClassifier",
]
