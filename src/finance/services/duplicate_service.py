"""
Duplicate Service - Bridge between UI/CLI and Duplicate Detection Logic.

This service wraps the DuplicateDetector and handles the lifecycle of duplicate
resolution events. It ensures that user decisions are captured as events to
improve future detection.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from finance.model.duplicate import DuplicateMatch
from finance.model.events import DuplicateConfirmed, DuplicateRejected
from finance.storage.event_store import EventStore
from finance.transfer.duplicate_detector import DuplicateDetector


from finance.model.account import Transaction

class DuplicateService:
    """Service for detecting and resolving duplicate transactions."""

    def __init__(self, detector: DuplicateDetector, event_store: EventStore):
        """Initialize service with detector and event store.

        Args:
            detector: Initialized DuplicateDetector instance
            event_store: EventStore for recording user decisions
        """
        self.detector = detector
        self.event_store = event_store

    def scan_transactions(
        self,
        transactions: List[Transaction],
        max_days_apart: int = 1,
        amount_tolerance: float = 0.001,
    ) -> List[DuplicateMatch]:
        """Scan a list of transactions for duplicates.

        Args:
            transactions: List of transactions to scan
            max_days_apart: Maximum days between potential duplicates
            amount_tolerance: Acceptable difference in amounts

        Returns:
            List of detected duplicate matches
        """
        # Get raw matches from detector
        matches = self.detector.scan_transactions(
            transactions, max_days_apart, amount_tolerance
        )

        # Filter out already resolved pairs
        resolved_pairs = self._get_resolved_pairs()

        filtered_matches = []
        for match in matches:
            pair_key = tuple(sorted([match.pair.txn1_id, match.pair.txn2_id]))
            if pair_key not in resolved_pairs:
                filtered_matches.append(match)

        return filtered_matches

    def _get_resolved_pairs(self) -> set[tuple[str, str]]:
        """Get set of resolved transaction pairs from event store."""
        resolved = set()

        # Get rejected duplicates
        rejected_events = self.event_store.get_events_by_type("DuplicateRejected")
        for event in rejected_events:
            if isinstance(event, DuplicateRejected):
                pair = tuple(sorted([event.transaction_id_1, event.transaction_id_2]))
                resolved.add(pair)

        # Get confirmed duplicates
        confirmed_events = self.event_store.get_events_by_type("DuplicateConfirmed")
        for event in confirmed_events:
            if isinstance(event, DuplicateConfirmed):
                pair = tuple(sorted([event.primary_transaction_id, event.duplicate_transaction_id]))
                resolved.add(pair)

        return resolved

    def scan_for_duplicates(
        self,
        data_dir: Path,
        max_days_apart: int = 1,
        amount_tolerance: float = 0.001,
    ) -> List[DuplicateMatch]:
        """Scan for potential duplicates in the given data directory.

        Args:
            data_dir: Directory containing ledger CSVs
            max_days_apart: Maximum days between potential duplicates
            amount_tolerance: Acceptable difference in amounts

        Returns:
            List of detected duplicate matches
        """
        return self.detector.scan_for_duplicates(
            data_dir, max_days_apart, amount_tolerance
        )

    def resolve_duplicate(
        self,
        match: DuplicateMatch,
        is_duplicate: bool,
        keep_id: Optional[str] = None,
        rationale: Optional[str] = None,
    ) -> None:
        """Resolve a potential duplicate match based on user input.

        Records the decision in the event store to train the model.

        Args:
            match: The duplicate match being resolved
            is_duplicate: True if user confirms it is a duplicate
            keep_id: ID of the transaction to keep (required if is_duplicate=True)
            rationale: User's explanation (optional, useful for rejections)
        """
        if is_duplicate:
            if not keep_id:
                raise ValueError("keep_id is required when confirming a duplicate")

            # Determine which is primary and which is duplicate
            if match.pair.txn1_id == keep_id:
                duplicate_id = match.pair.txn2_id
                canonical_desc = match.pair.txn1_description
            elif match.pair.txn2_id == keep_id:
                duplicate_id = match.pair.txn1_id
                canonical_desc = match.pair.txn2_description
            else:
                raise ValueError(f"keep_id {keep_id} not found in match pair")

            event = DuplicateConfirmed(
                suggestion_event_id="manual_scan",  # TODO: Link to actual suggestion event if available
                primary_transaction_id=keep_id,
                duplicate_transaction_id=duplicate_id,
                canonical_description=canonical_desc,
                user_rationale=rationale,
                llm_was_correct=(match.assessment.is_duplicate == is_duplicate),
            )
        else:
            event = DuplicateRejected(
                suggestion_event_id="manual_scan",
                transaction_id_1=match.pair.txn1_id,
                transaction_id_2=match.pair.txn2_id,
                user_rationale=rationale,
                llm_was_correct=(match.assessment.is_duplicate == is_duplicate),
            )

        self.event_store.append_event(event)
