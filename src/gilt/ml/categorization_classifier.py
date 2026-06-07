"""Transaction categorization classifier using ML.

Trains a classifier from user categorization events to automatically
categorize new transactions based on their descriptions and amounts.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from gilt.ml.categorization_training_builder import CategorizationTrainingBuilder
from gilt.ml.merchant_normalizer import is_income_category
from gilt.storage.event_store import EventStore


class CategorizationClassifier:
    """ML classifier for automatic transaction categorization.

    Uses LogisticRegression to predict categories based on:
    - Transaction description normalized via merchant_normalizer (TF-IDF features)
    - Account (one-hot encoded)
    - Transaction amount (log-scaled magnitude and direction)

    Training data comes from user categorization events in the event store.
    A hard direction constraint is applied at predict time: outflows cannot
    be assigned income categories and inflows cannot be assigned non-income ones.
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
        self.classifier = LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=random_state,
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

        Applies a hard direction constraint before selecting the best category:
        - Outflows (amount < 0) cannot be assigned income categories.
        - Inflows (amount > 0) cannot be assigned non-income categories.
        If the constraint zeroes all probability mass the result is (None, 0.0).

        Args:
            transaction_data: List of transaction dicts with description, amount, etc.
            confidence_threshold: Minimum confidence to return prediction (0.0-1.0)

        Returns:
            List of (category, confidence) tuples. Category is None if confidence
            is below threshold or no valid category exists after direction masking.
        """
        if not self.is_trained:
            raise ValueError("Classifier not trained. Call train() first.")

        if not transaction_data:
            return []

        # Precompute per-category income flag
        income_mask = np.array([is_income_category(cat) for cat in self.category_names], dtype=bool)

        # Build features
        features = self.training_builder.build_features(transaction_data)

        # Get raw probabilities
        probabilities = self.classifier.predict_proba(features)

        results = []
        for txn, probs in zip(transaction_data, probabilities, strict=False):
            amount = txn.get("amount", 0.0)
            masked = probs.copy()

            # Apply direction constraint
            if amount < 0:
                # Outflow: zero income category mass
                masked[income_mask] = 0.0
            elif amount > 0:
                # Inflow: zero non-income category mass
                masked[~income_mask] = 0.0

            total_mass = masked.sum()
            if total_mass == 0.0:
                results.append((None, 0.0))
                continue

            # Renormalize and pick best
            masked /= total_mass
            best_idx = int(np.argmax(masked))
            confidence = float(masked[best_idx])

            category = self.category_names[best_idx] if confidence >= confidence_threshold else None
            results.append((category, confidence))

        return results

    def predict_topk(
        self,
        transaction_data: list[dict],
        k: int = 3,
    ) -> list[list[tuple[str, float]]]:
        """Predict top-k categories with calibrated confidences for each transaction.

        Useful for --explain output. Direction constraint is applied before ranking.

        Args:
            transaction_data: List of transaction dicts with description, amount, etc.
            k: Number of top candidates to return per transaction

        Returns:
            List of lists; each inner list contains up to k (category, confidence) tuples
            sorted by confidence descending.
        """
        if not self.is_trained:
            raise ValueError("Classifier not trained. Call train() first.")

        if not transaction_data:
            return []

        income_mask = np.array([is_income_category(cat) for cat in self.category_names], dtype=bool)

        features = self.training_builder.build_features(transaction_data)
        probabilities = self.classifier.predict_proba(features)

        all_topk: list[list[tuple[str, float]]] = []
        for txn, probs in zip(transaction_data, probabilities, strict=False):
            amount = txn.get("amount", 0.0)
            masked = probs.copy()

            if amount < 0:
                masked[income_mask] = 0.0
            elif amount > 0:
                masked[~income_mask] = 0.0

            total_mass = masked.sum()
            if total_mass > 0.0:
                masked /= total_mass

            top_indices = np.argsort(masked)[::-1][:k]
            topk = [
                (self.category_names[i], float(masked[i])) for i in top_indices if masked[i] > 0.0
            ]
            all_topk.append(topk)

        return all_topk

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

        For LogisticRegression, importance is the mean absolute coefficient
        across all class-vs-rest decision boundaries.

        Args:
            top_n: Number of top features to return

        Returns:
            List of (feature_name, importance) tuples sorted by importance descending.
            Importance values are mean absolute logistic regression coefficients,
            normalized to [0, 1] relative to the maximum.
        """
        if not self.is_trained:
            raise ValueError("Classifier not trained. Call train() first.")

        # Build full feature name list: TF-IDF terms + account categories + scalars
        tfidf_names = list(self.training_builder.vectorizer.get_feature_names_out())
        account_names = [
            f"account_{cat}" for cat in self.training_builder._account_encoder.categories_[0]
        ]
        scalar_names = ["log_amount", "direction"]
        feature_names = tfidf_names + account_names + scalar_names

        # Mean absolute coefficient across all classes (shape: n_features)
        coef = self.classifier.coef_  # shape: (n_classes, n_features) or (1, n_features)
        importances = np.mean(np.abs(coef), axis=0)

        # Normalize to [0, 1]
        max_imp = importances.max()
        if max_imp > 0:
            importances = importances / max_imp

        # Guard against feature name / coefficient count mismatch
        n = min(len(feature_names), len(importances))
        importances = importances[:n]
        feature_names = feature_names[:n]

        # Sort by importance descending
        indices = np.argsort(importances)[::-1][:top_n]
        return [(feature_names[i], float(importances[i])) for i in indices]


__all__ = [
    "CategorizationClassifier",
]
