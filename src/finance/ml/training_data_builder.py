"""Training data builder for duplicate detection classifier.

Extracts labeled transaction pairs from user feedback events to train
the ML classifier. Converts DuplicateConfirmed and DuplicateRejected events
into training examples.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List, Tuple

from finance.model.duplicate import TransactionPair
from finance.model.events import DuplicateConfirmed, DuplicateRejected
from finance.storage.event_store import EventStore


class TrainingDataBuilder:
    """Builds training datasets from user feedback events."""

    def __init__(self, event_store: EventStore):
        """Initialize with event store.

        Args:
            event_store: Event store containing user feedback
        """
        self.event_store = event_store

    def load_from_events(self) -> Tuple[List[TransactionPair], List[bool]]:
        """Load training examples from DuplicateConfirmed/Rejected events.

        Returns:
            Tuple of (pairs, labels) where labels are True for duplicates
        """
        pairs: List[TransactionPair] = []
        labels: List[bool] = []

        # First, build index of suggestion events by ID
        suggestion_events = self.event_store.get_events_by_type("DuplicateSuggested")
        suggestions_by_id = {event.event_id: event for event in suggestion_events}

        # Get all duplicate-related events
        confirmed_events = self.event_store.get_events_by_type("DuplicateConfirmed")
        rejected_events = self.event_store.get_events_by_type("DuplicateRejected")

        # Process confirmed duplicates (positive examples)
        for event in confirmed_events:
            if isinstance(event, DuplicateConfirmed):
                pair = self._confirmed_event_to_pair(event, suggestions_by_id)
                if pair:
                    pairs.append(pair)
                    labels.append(True)

        # Process rejected duplicates (negative examples)
        for event in rejected_events:
            if isinstance(event, DuplicateRejected):
                pair = self._rejected_event_to_pair(event, suggestions_by_id)
                if pair:
                    pairs.append(pair)
                    labels.append(False)

        return pairs, labels

    def _confirmed_event_to_pair(
        self,
        event: DuplicateConfirmed,
        suggestions_by_id: dict,
    ) -> TransactionPair | None:
        """Reconstruct TransactionPair from DuplicateConfirmed event.

        Args:
            event: DuplicateConfirmed event
            suggestions_by_id: Index of DuplicateSuggested events

        Returns:
            TransactionPair or None if reconstruction fails
        """
        try:
            # Get the original suggestion
            suggestion = suggestions_by_id.get(event.suggestion_event_id)
            if not suggestion or 'assessment' not in suggestion.__dict__:
                return None

            # Extract pair data from assessment
            assessment = suggestion.assessment
            if 'pair' not in assessment:
                return None

            pair_data = assessment['pair']
            return TransactionPair(**pair_data)

        except (ValueError, AttributeError, TypeError, KeyError) as e:
            # Log error but continue processing
            return None

    def _rejected_event_to_pair(
        self,
        event: DuplicateRejected,
        suggestions_by_id: dict,
    ) -> TransactionPair | None:
        """Reconstruct TransactionPair from DuplicateRejected event.

        Args:
            event: DuplicateRejected event
            suggestions_by_id: Index of DuplicateSuggested events

        Returns:
            TransactionPair or None if reconstruction fails
        """
        try:
            # Get the original suggestion
            suggestion = suggestions_by_id.get(event.suggestion_event_id)
            if not suggestion or 'assessment' not in suggestion.__dict__:
                return None

            # Extract pair data from assessment
            assessment = suggestion.assessment
            if 'pair' not in assessment:
                return None

            pair_data = assessment['pair']
            return TransactionPair(**pair_data)

        except (ValueError, AttributeError, TypeError, KeyError) as e:
            # Log error but continue processing
            return None

    def get_statistics(self) -> dict:
        """Get statistics about available training data.

        Returns:
            Dictionary with counts and balance information
        """
        pairs, labels = self.load_from_events()

        n_positive = sum(labels)
        n_negative = len(labels) - n_positive

        return {
            'total_examples': len(pairs),
            'positive_examples': n_positive,
            'negative_examples': n_negative,
            'class_balance': n_positive / len(labels) if len(labels) > 0 else 0.0,
            'sufficient_for_training': len(pairs) >= 10,
        }


__all__ = ["TrainingDataBuilder"]
