"""
Duplicate review service - functional core for duplicate transaction review workflow.

This service extracts all business logic from the CLI command, making it testable
without UI dependencies. It handles:
- Creating suggestion events with correct schema
- Processing user decisions into appropriate events
- Calculating smart defaults from learned patterns
- Building review summaries

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt

All dependencies are injected. All functions return data structures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from gilt.model.duplicate import TransactionPair, DuplicateAssessment, DuplicateMatch
from gilt.model.events import DuplicateSuggested, DuplicateConfirmed, DuplicateRejected, Event
from gilt.storage.event_store import EventStore


@dataclass
class ReviewSummary:
    """Summary statistics for a duplicate review session."""

    total_matches: int
    llm_predicted_duplicates: int
    llm_predicted_not_duplicates: int
    user_confirmed: int
    user_rejected: int
    feedback_count: int


@dataclass
class UserDecision:
    """User's decision about a duplicate suggestion."""

    choice: str  # "1" (use latest), "2" (use original), "N" (reject)
    rationale: Optional[str] = None


@dataclass
class SmartDefault:
    """Smart default suggestion based on learned patterns."""

    default_choice: str  # "1" or "2"
    hint: str  # Hint text to display (empty if no pattern)


class DuplicateReviewService:
    """
    Service for duplicate transaction review workflow.

    This is the functional core - pure business logic with no I/O or UI dependencies.
    All state changes are expressed as events that are emitted to the event store.

    Responsibilities:
    - Create properly structured suggestion events
    - Process user decisions into confirm/reject events
    - Calculate smart defaults from learned patterns
    - Build summary statistics

    Does NOT:
    - Display anything to console
    - Read from files directly
    - Prompt users for input
    - Format output for display
    """

    def __init__(self, event_store: EventStore):
        """
        Initialize the service.

        Args:
            event_store: Event store for persisting events
        """
        self.event_store = event_store

    def create_suggestion_event(
        self,
        pair: TransactionPair,
        assessment: DuplicateAssessment,
        model: str,
        prompt_version: str,
    ) -> tuple[DuplicateSuggested, str]:
        """
        Create and emit a DuplicateSuggested event.

        CRITICAL: This uses ONLY the fields that exist on DuplicateAssessment:
        - is_duplicate
        - confidence
        - reasoning

        NOT the non-existent fields that caused the bug:
        - same_date (doesn't exist)
        - same_amount (doesn't exist)
        - same_account (doesn't exist)
        - description_similarity (doesn't exist)

        Args:
            pair: The transaction pair being assessed
            assessment: LLM's assessment with is_duplicate, confidence, reasoning
            model: Model name used for assessment
            prompt_version: Version of prompt template used

        Returns:
            Tuple of (event, event_id)
        """
        event = DuplicateSuggested(
            transaction_id_1=pair.txn1_id,
            transaction_id_2=pair.txn2_id,
            confidence=assessment.confidence,
            reasoning=assessment.reasoning,
            model=model,
            prompt_version=prompt_version,
            assessment={
                "is_duplicate": assessment.is_duplicate,
                "confidence": assessment.confidence,
                "reasoning": assessment.reasoning,
                "pair": pair.model_dump(),  # Include complete transaction pair for ML training
            },
        )

        self.event_store.append_event(event)
        return event, event.event_id

    def process_user_decision(
        self,
        decision: UserDecision,
        pair: TransactionPair,
        assessment: DuplicateAssessment,
        suggestion_id: str,
    ) -> tuple[Event, str]:
        """
        Process user's decision and create appropriate event.

        Args:
            decision: User's choice and optional rationale
            pair: The transaction pair
            assessment: LLM's original assessment
            suggestion_id: ID of the suggestion event being responded to

        Returns:
            Tuple of (event, action) where action is "confirmed" or "rejected"
        """
        if decision.choice.upper() == "N":
            # User rejects duplicate
            event = DuplicateRejected(
                suggestion_event_id=suggestion_id,
                transaction_id_1=pair.txn1_id,
                transaction_id_2=pair.txn2_id,
                user_rationale=decision.rationale if decision.rationale else None,
                llm_was_correct=False,  # User says not duplicate, so LLM was wrong
            )
            self.event_store.append_event(event)
            return event, "rejected"

        else:
            # User confirms duplicate
            if decision.choice == "1":
                # Use latest (txn2) description
                canonical_desc = pair.txn2_description
            else:
                # Use original (txn1) description
                canonical_desc = pair.txn1_description

            event = DuplicateConfirmed(
                suggestion_event_id=suggestion_id,
                primary_transaction_id=pair.txn1_id,
                duplicate_transaction_id=pair.txn2_id,
                canonical_description=canonical_desc,
                user_rationale=decision.rationale if decision.rationale else None,
                llm_was_correct=assessment.is_duplicate,
            )
            self.event_store.append_event(event)
            return event, "confirmed"

    def calculate_smart_default(self, learned_patterns: list[str]) -> SmartDefault:
        """
        Calculate smart default choice from learned patterns.

        Analyzes learned patterns to determine if user has a preference for
        original vs. latest description format.

        Args:
            learned_patterns: List of learned pattern strings from prompt manager

        Returns:
            SmartDefault with default choice and hint text
        """
        default_choice = "1"  # Default to latest
        hint = ""

        # Check for description preference patterns
        for pattern in learned_patterns:
            if "User prefers latest" in pattern:
                default_choice = "1"
                # Extract percentage if present
                match = re.search(r'(\d+)%', pattern)
                if match:
                    pct = match.group(1)
                    hint = f" [dim](learned: {pct}% prefer latest)[/dim]"
                else:
                    hint = " [dim](learned: prefer latest)[/dim]"
                break
            elif "User prefers original" in pattern:
                default_choice = "2"
                # Extract percentage if present
                match = re.search(r'(\d+)%', pattern)
                if match:
                    pct = match.group(1)
                    hint = f" [dim](learned: {pct}% prefer original)[/dim]"
                else:
                    hint = " [dim](learned: prefer original)[/dim]"
                break

        return SmartDefault(default_choice=default_choice, hint=hint)

    def build_summary(
        self,
        matches: list[DuplicateMatch],
        feedback: list[tuple[UserDecision, Event, str]],
    ) -> ReviewSummary:
        """
        Build summary statistics for review session.

        Args:
            matches: All matches analyzed by LLM
            feedback: List of (decision, event, action) tuples from interactive session

        Returns:
            ReviewSummary with statistics
        """
        # Count LLM predictions
        llm_predicted_duplicates = sum(
            1 for m in matches if m.assessment.is_duplicate
        )
        llm_predicted_not_duplicates = len(matches) - llm_predicted_duplicates

        # Count user feedback
        user_confirmed = sum(
            1 for _, _, action in feedback if action == "confirmed"
        )
        user_rejected = sum(
            1 for _, _, action in feedback if action == "rejected"
        )

        return ReviewSummary(
            total_matches=len(matches),
            llm_predicted_duplicates=llm_predicted_duplicates,
            llm_predicted_not_duplicates=llm_predicted_not_duplicates,
            user_confirmed=user_confirmed,
            user_rejected=user_rejected,
            feedback_count=len(feedback),
        )


__all__ = [
    "DuplicateReviewService",
    "ReviewSummary",
    "UserDecision",
    "SmartDefault",
]
