"""Training data builder for transaction categorization classifier.

Extracts labeled transaction categorizations from user events to train
an ML classifier that can automatically categorize new transactions.
"""

from __future__ import annotations

from typing import List, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from gilt.model.events import TransactionCategorized, TransactionImported
from gilt.storage.event_store import EventStore


class CategorizationTrainingBuilder:
    """Builds training datasets from TransactionCategorized events.

    Extracts features from transaction descriptions and learns to predict
    categories based on user categorization decisions.
    """

    def __init__(self, event_store: EventStore):
        """Initialize with event store.

        Args:
            event_store: Event store containing categorization events
        """
        self.event_store = event_store
        self.vectorizer = TfidfVectorizer(
            analyzer="word",
            lowercase=True,
            ngram_range=(1, 2),  # Unigrams and bigrams
            max_features=1000,
            min_df=1,  # Include even rare terms (changed from 2)
        )
        self._is_fitted = False

    def load_from_events(self, source_filter: str = "user") -> Tuple[List[dict], List[str]]:
        """Load training examples from TransactionCategorized events.

        Args:
            source_filter: Only include categorizations from this source
                          ("user", "llm", or "rule"). Default: "user"

        Returns:
            Tuple of (transaction_data, category_labels)
            - transaction_data: List of dicts with transaction info
            - category_labels: List of "Category:Subcategory" strings
        """
        transaction_data: List[dict] = []
        category_labels: List[str] = []

        # Get all categorization events from specified source
        events = self.event_store.get_events_by_type("TransactionCategorized")

        for event in events:
            if isinstance(event, TransactionCategorized):
                # Filter by source (user vs llm vs rule)
                if event.source != source_filter:
                    continue

                # Get transaction details from ImportedTransaction events
                txn_events = self.event_store.get_events(
                    aggregate_type="transaction",
                    aggregate_id=event.transaction_id,
                )

                # Find the most recent TransactionImported for this ID
                txn_import = None
                for txn_event in reversed(txn_events):
                    if isinstance(txn_event, TransactionImported):
                        txn_import = txn_event
                        break

                if not txn_import:
                    # Can't get transaction details, skip
                    continue

                # Extract transaction features
                txn_data = {
                    "transaction_id": event.transaction_id,
                    "description": txn_import.raw_description,
                    "amount": float(txn_import.amount),
                    "account": txn_import.source_account,
                    "date": txn_import.transaction_date,
                }
                transaction_data.append(txn_data)

                # Build category label
                if event.subcategory:
                    label = f"{event.category}:{event.subcategory}"
                else:
                    label = event.category

                category_labels.append(label)

        return transaction_data, category_labels

    def build_features(self, transaction_data: List[dict]) -> np.ndarray:
        """Build feature vectors from transaction data.

        Features include:
        - TF-IDF vectors from description text
        - Amount (normalized)
        - Account (one-hot encoded)

        Args:
            transaction_data: List of transaction dicts with description, amount, account

        Returns:
            Feature matrix (n_transactions x n_features)
        """
        if not transaction_data:
            return np.array([])

        # Extract descriptions for TF-IDF
        descriptions = [txn["description"] for txn in transaction_data]

        # Fit or transform TF-IDF
        if not self._is_fitted:
            text_features = self.vectorizer.fit_transform(descriptions)
            self._is_fitted = True
        else:
            text_features = self.vectorizer.transform(descriptions)

        # Extract numeric features
        amounts = np.array([txn["amount"] for txn in transaction_data]).reshape(-1, 1)

        # Normalize amounts (log transform for better distribution)
        amounts_normalized = np.sign(amounts) * np.log1p(np.abs(amounts))

        # Combine text and numeric features
        text_array = text_features.toarray()  # type: ignore[attr-defined]
        features = np.hstack([text_array, amounts_normalized])

        return features

    def get_training_data(
        self,
        source_filter: str = "user",
        min_samples_per_category: int = 2,
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Get complete training dataset with features and labels.

        Args:
            source_filter: Only include categorizations from this source
            min_samples_per_category: Minimum samples required per category
                                     (categories with fewer are excluded)

        Returns:
            Tuple of (features, labels, category_names)
            - features: Feature matrix (n_samples x n_features)
            - labels: Integer category labels (n_samples,)
            - category_names: List mapping label indices to category names
        """
        # Load raw data
        transaction_data, category_labels = self.load_from_events(source_filter)

        if not transaction_data:
            return np.array([]), np.array([]), []

        # Filter out categories with too few samples
        from collections import Counter

        category_counts = Counter(category_labels)
        valid_categories = {
            cat for cat, count in category_counts.items() if count >= min_samples_per_category
        }

        # Filter data
        filtered_txns = []
        filtered_labels = []
        for txn, label in zip(transaction_data, category_labels):
            if label in valid_categories:
                filtered_txns.append(txn)
                filtered_labels.append(label)

        if not filtered_txns:
            return np.array([]), np.array([]), []

        # Build features
        features = self.build_features(filtered_txns)

        # Convert category labels to integers
        unique_categories = sorted(set(filtered_labels))
        category_to_idx = {cat: idx for idx, cat in enumerate(unique_categories)}
        label_indices = np.array([category_to_idx[cat] for cat in filtered_labels])

        return features, label_indices, unique_categories


__all__ = [
    "CategorizationTrainingBuilder",
]
