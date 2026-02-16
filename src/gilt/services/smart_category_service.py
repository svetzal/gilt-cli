"""
Smart Category Service - Bridge between UI/CLI and ML Categorization.

This service wraps the CategorizationClassifier and handles the lifecycle of
categorization events. It provides predictions for UI suggestions and records
user choices to train the model.
"""

from __future__ import annotations

from typing import Optional, Tuple

from gilt.ml.categorization_classifier import CategorizationClassifier
from gilt.model.events import TransactionCategorized
from gilt.storage.event_store import EventStore


class SmartCategoryService:
    """Service for ML-assisted transaction categorization."""

    def __init__(self, classifier: CategorizationClassifier, event_store: EventStore):
        """Initialize service with classifier and event store.

        Args:
            classifier: Initialized CategorizationClassifier instance
            event_store: EventStore for recording user decisions
        """
        self.classifier = classifier
        self.event_store = event_store

    def predict_category(
        self,
        description: str,
        amount: float,
        account: str,
    ) -> Tuple[Optional[str], float]:
        """Predict category for a transaction.

        Args:
            description: Transaction description
            amount: Transaction amount
            account: Account ID

        Returns:
            Tuple of (predicted_category, confidence_score)
        """
        # We pass 0.0 threshold because we want the raw prediction to show
        # in the UI (even if low confidence), letting the UI decide how to present it.
        try:
            if not self.classifier.is_trained:
                # Try to train on the fly if we have data
                try:
                    self.classifier.train()
                except ValueError:
                    # Not enough data to train
                    return None, 0.0

            return self.classifier.predict_single(
                description=description,
                amount=amount,
                account=account,
                confidence_threshold=0.0,
            )
        except Exception:
            # Fallback if prediction fails
            return None, 0.0

    def record_categorization(
        self,
        transaction_id: str,
        category: str,
        source: str = "user",
        subcategory: Optional[str] = None,
        confidence: Optional[float] = None,
        previous_category: Optional[str] = None,
        previous_subcategory: Optional[str] = None,
        rationale: Optional[str] = None,
    ) -> None:
        """Record a categorization decision.

        Args:
            transaction_id: ID of the transaction
            category: Assigned category
            source: Who assigned it ("user", "llm", "rule")
            subcategory: Assigned subcategory (optional)
            confidence: Confidence score if available
            previous_category: Previous category (for undo/history)
            previous_subcategory: Previous subcategory
            rationale: Explanation for the decision
        """
        event = TransactionCategorized(
            transaction_id=transaction_id,
            category=category,
            subcategory=subcategory,
            source=source,
            confidence=confidence,
            previous_category=previous_category,
            previous_subcategory=previous_subcategory,
            rationale=rationale,
        )
        self.event_store.append_event(event)

    def train_model(self) -> dict:
        """Trigger model retraining from event store.

        Returns:
            Training metrics
        """
        return self.classifier.train()
