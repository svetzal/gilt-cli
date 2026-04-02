"""
Tests for DuplicateReviewService.

These tests verify the functional core logic for duplicate review workflow,
ensuring that all business logic is testable without CLI/GUI dependencies.

CRITICAL: These tests catch bugs that weren't caught before, specifically:
- Correct DuplicateAssessment field usage (is_duplicate, confidence, reasoning)
- NOT the non-existent fields (same_date, same_amount, same_account, description_similarity)
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, Mock

import pytest

from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair
from gilt.model.events import DuplicateConfirmed, DuplicateRejected, DuplicateSuggested
from gilt.services.duplicate_review_service import (
    DuplicateReviewService,
    UserDecision,
)


class DescribeDuplicateReviewService:
    """Tests for DuplicateReviewService."""

    @pytest.fixture
    def mock_event_store(self):
        """Create mock event store."""
        mock = Mock()
        mock.append_event = Mock()
        return mock

    @pytest.fixture
    def service(self, mock_event_store):
        """Create service instance."""
        return DuplicateReviewService(event_store=mock_event_store)

    @pytest.fixture
    def sample_pair(self):
        """Create sample transaction pair."""
        return TransactionPair(
            txn1_id="abc123def456",
            txn1_date=date(2025, 11, 15),
            txn1_description="SPOTIFY PREMIUM",
            txn1_amount=-10.99,
            txn1_account="MYBANK_CHQ",
            txn2_id="xyz789uvw012",
            txn2_date=date(2025, 11, 15),
            txn2_description="SPOTIFY PREMIUM ON",
            txn2_amount=-10.99,
            txn2_account="MYBANK_CHQ",
        )

    @pytest.fixture
    def sample_assessment(self):
        """Create sample assessment with CORRECT fields."""
        return DuplicateAssessment(
            is_duplicate=True,
            confidence=0.95,
            reasoning=(
                "Same amount, same date, similar description pattern for Spotify subscription"
            ),
        )


class DescribeSuggestionEventCreation(DescribeDuplicateReviewService):
    """Tests for create_suggestion_event method."""

    def it_should_create_event_with_correct_schema(
        self, service, mock_event_store, sample_pair, sample_assessment
    ):
        """Should create DuplicateSuggested event with correct fields."""
        model = "qwen3.5:27b"
        prompt_version = "v2.1"

        event, event_id = service.create_suggestion_event(
            pair=sample_pair,
            assessment=sample_assessment,
            model=model,
            prompt_version=prompt_version,
        )

        # Verify event type
        assert isinstance(event, DuplicateSuggested)
        assert event.event_type == "DuplicateSuggested"

        # Verify transaction IDs
        assert event.transaction_id_1 == sample_pair.txn1_id
        assert event.transaction_id_2 == sample_pair.txn2_id

        # Verify assessment data (CORRECT fields)
        assert event.confidence == sample_assessment.confidence
        assert event.reasoning == sample_assessment.reasoning
        assert event.model == model
        assert event.prompt_version == prompt_version

        # Verify assessment dict contains CORRECT fields
        assert event.assessment["is_duplicate"] == sample_assessment.is_duplicate
        assert event.assessment["confidence"] == sample_assessment.confidence
        assert event.assessment["reasoning"] == sample_assessment.reasoning

        # Verify event was appended to store
        mock_event_store.append_event.assert_called_once_with(event)

        # Verify event_id is returned
        assert event_id == event.event_id

    def it_should_not_access_nonexistent_assessment_fields(
        self, service, mock_event_store, sample_pair, sample_assessment
    ):
        """
        CRITICAL BUG TEST: Should NOT try to access fields that don't exist
        on DuplicateAssessment (same_date, same_amount, same_account, description_similarity).

        This test would have caught the bug in duplicates.py!
        """
        event, _ = service.create_suggestion_event(
            pair=sample_pair,
            assessment=sample_assessment,
            model="qwen3.5:27b",
            prompt_version="v2.1",
        )

        # These fields should NOT be in the assessment dict
        assert "same_date" not in event.assessment
        assert "same_amount" not in event.assessment
        assert "same_account" not in event.assessment
        assert "description_similarity" not in event.assessment

        # Required fields for assessment (updated to include 'pair' for ML training)
        assert set(event.assessment.keys()) == {
            "is_duplicate",
            "confidence",
            "reasoning",
            "pair",  # Complete TransactionPair data for ML training
        }

        # Verify pair contains complete transaction data
        assert event.assessment["pair"]["txn1_id"] == sample_pair.txn1_id
        assert event.assessment["pair"]["txn2_id"] == sample_pair.txn2_id


class DescribeUserDecisionProcessing(DescribeDuplicateReviewService):
    """Tests for process_user_decision method."""

    def it_should_create_confirmed_event_for_use_latest_choice(
        self, service, mock_event_store, sample_pair, sample_assessment
    ):
        """Should create DuplicateConfirmed event when user chooses latest description."""
        decision = UserDecision(choice="1", rationale="Latest format is clearer")
        suggestion_id = "suggestion-event-123"

        event, action = service.process_user_decision(
            decision=decision,
            pair=sample_pair,
            assessment=sample_assessment,
            suggestion_id=suggestion_id,
        )

        # Verify event type
        assert isinstance(event, DuplicateConfirmed)
        assert event.event_type == "DuplicateConfirmed"

        # Verify linkage
        assert event.suggestion_event_id == suggestion_id

        # Verify IDs
        assert event.primary_transaction_id == sample_pair.txn1_id
        assert event.duplicate_transaction_id == sample_pair.txn2_id

        # Verify description choice (latest = txn2)
        assert event.canonical_description == sample_pair.txn2_description

        # Verify rationale
        assert event.user_rationale == "Latest format is clearer"

        # Verify LLM correctness
        assert event.llm_was_correct == sample_assessment.is_duplicate

        # Verify event was appended
        mock_event_store.append_event.assert_called_once_with(event)

        # Verify action
        assert action == "confirmed"

    def it_should_create_confirmed_event_for_use_original_choice(
        self, service, mock_event_store, sample_pair, sample_assessment
    ):
        """Should create DuplicateConfirmed event when user chooses original description."""
        decision = UserDecision(choice="2", rationale=None)
        suggestion_id = "suggestion-event-456"

        event, action = service.process_user_decision(
            decision=decision,
            pair=sample_pair,
            assessment=sample_assessment,
            suggestion_id=suggestion_id,
        )

        # Verify event type
        assert isinstance(event, DuplicateConfirmed)

        # Verify description choice (original = txn1)
        assert event.canonical_description == sample_pair.txn1_description

        # Verify no rationale
        assert event.user_rationale is None

        # Verify action
        assert action == "confirmed"

    def it_should_create_rejected_event_for_no_choice(
        self, service, mock_event_store, sample_pair, sample_assessment
    ):
        """Should create DuplicateRejected event when user rejects duplicate."""
        decision = UserDecision(choice="N", rationale="Different purchases")
        suggestion_id = "suggestion-event-789"

        event, action = service.process_user_decision(
            decision=decision,
            pair=sample_pair,
            assessment=sample_assessment,
            suggestion_id=suggestion_id,
        )

        # Verify event type
        assert isinstance(event, DuplicateRejected)
        assert event.event_type == "DuplicateRejected"

        # Verify linkage
        assert event.suggestion_event_id == suggestion_id

        # Verify IDs
        assert event.transaction_id_1 == sample_pair.txn1_id
        assert event.transaction_id_2 == sample_pair.txn2_id

        # Verify rationale
        assert event.user_rationale == "Different purchases"

        # Verify LLM correctness (was wrong if user rejects)
        assert event.llm_was_correct is False

        # Verify event was appended
        mock_event_store.append_event.assert_called_once_with(event)

        # Verify action
        assert action == "rejected"

    def it_should_handle_lowercase_n_for_reject(
        self, service, mock_event_store, sample_pair, sample_assessment
    ):
        """Should handle lowercase 'n' as rejection."""
        decision = UserDecision(choice="n", rationale=None)
        suggestion_id = "suggestion-event-999"

        event, action = service.process_user_decision(
            decision=decision,
            pair=sample_pair,
            assessment=sample_assessment,
            suggestion_id=suggestion_id,
        )

        assert isinstance(event, DuplicateRejected)
        assert action == "rejected"


class DescribeSmartDefaultCalculation(DescribeDuplicateReviewService):
    """Tests for calculate_smart_default method."""

    def it_should_default_to_latest_when_no_patterns(self, service):
        """Should default to latest description when no learned patterns exist."""
        learned_patterns = []

        smart_default = service.calculate_smart_default(learned_patterns)

        assert smart_default.default_choice == "1"
        assert smart_default.hint == ""

    def it_should_prefer_latest_when_pattern_indicates(self, service):
        """Should prefer latest when learned pattern indicates user preference."""
        learned_patterns = [
            "User prefers latest description format (85% of confirmations)",
            "Other pattern here",
        ]

        smart_default = service.calculate_smart_default(learned_patterns)

        assert smart_default.default_choice == "1"
        assert "85%" in smart_default.hint
        assert "latest" in smart_default.hint

    def it_should_prefer_original_when_pattern_indicates(self, service):
        """Should prefer original when learned pattern indicates user preference."""
        learned_patterns = [
            "Some pattern",
            "User prefers original description format (70% of confirmations)",
        ]

        smart_default = service.calculate_smart_default(learned_patterns)

        assert smart_default.default_choice == "2"
        assert "70%" in smart_default.hint
        assert "original" in smart_default.hint

    def it_should_extract_percentage_from_pattern(self, service):
        """Should extract percentage from learned pattern."""
        learned_patterns = [
            "User prefers latest description format (92% of confirmations)",
        ]

        smart_default = service.calculate_smart_default(learned_patterns)

        assert "92%" in smart_default.hint

    def it_should_default_to_latest_if_no_percentage_found(self, service):
        """Should default to latest if pattern doesn't contain percentage."""
        learned_patterns = [
            "User prefers latest description format",
        ]

        smart_default = service.calculate_smart_default(learned_patterns)

        assert smart_default.default_choice == "1"
        # Should still have hint even without percentage
        assert "latest" in smart_default.hint


class DescribeSummaryBuilding(DescribeDuplicateReviewService):
    """Tests for build_summary method."""

    def it_should_calculate_summary_with_no_feedback(self, service, sample_assessment):
        """Should calculate summary when no interactive feedback provided."""
        matches = [
            DuplicateMatch(
                pair=TransactionPair(
                    txn1_id="a1",
                    txn1_date=date(2025, 11, 1),
                    txn1_description="DESC1",
                    txn1_amount=-10.0,
                    txn1_account="ACC1",
                    txn2_id="a2",
                    txn2_date=date(2025, 11, 1),
                    txn2_description="DESC2",
                    txn2_amount=-10.0,
                    txn2_account="ACC1",
                ),
                assessment=DuplicateAssessment(is_duplicate=True, confidence=0.9, reasoning="test"),
            ),
            DuplicateMatch(
                pair=TransactionPair(
                    txn1_id="b1",
                    txn1_date=date(2025, 11, 2),
                    txn1_description="DESC3",
                    txn1_amount=-20.0,
                    txn1_account="ACC1",
                    txn2_id="b2",
                    txn2_date=date(2025, 11, 2),
                    txn2_description="DESC4",
                    txn2_amount=-20.0,
                    txn2_account="ACC1",
                ),
                assessment=DuplicateAssessment(
                    is_duplicate=False, confidence=0.3, reasoning="test"
                ),
            ),
        ]

        summary = service.build_summary(matches=matches, feedback=[])

        assert summary.total_matches == 2
        assert summary.llm_predicted_duplicates == 1
        assert summary.llm_predicted_not_duplicates == 1
        assert summary.user_confirmed == 0
        assert summary.user_rejected == 0
        assert summary.feedback_count == 0

    def it_should_calculate_summary_with_feedback(self, service, sample_pair, sample_assessment):
        """Should calculate summary including interactive feedback."""
        matches = [
            DuplicateMatch(pair=sample_pair, assessment=sample_assessment),
        ]

        decision1 = UserDecision(choice="1", rationale="test")
        event1 = DuplicateConfirmed(
            suggestion_event_id="s1",
            primary_transaction_id="p1",
            duplicate_transaction_id="d1",
            canonical_description="desc1",
            llm_was_correct=True,
        )

        decision2 = UserDecision(choice="N", rationale="test")
        event2 = DuplicateRejected(
            suggestion_event_id="s2",
            transaction_id_1="t1",
            transaction_id_2="t2",
            llm_was_correct=False,
        )

        feedback = [
            (decision1, event1, "confirmed"),
            (decision2, event2, "rejected"),
        ]

        summary = service.build_summary(matches=matches, feedback=feedback)

        assert summary.total_matches == 1
        assert summary.feedback_count == 2
        assert summary.user_confirmed == 1
        assert summary.user_rejected == 1

    def it_should_count_only_confirmed_and_rejected_in_feedback(
        self, service, sample_pair, sample_assessment
    ):
        """Should only count confirmed/rejected events in feedback statistics."""
        matches = [
            DuplicateMatch(pair=sample_pair, assessment=sample_assessment),
        ]

        # Mix of events
        feedback = [
            (
                UserDecision(choice="1", rationale=None),
                DuplicateConfirmed(
                    suggestion_event_id="s1",
                    primary_transaction_id="p1",
                    duplicate_transaction_id="d1",
                    canonical_description="desc",
                    llm_was_correct=True,
                ),
                "confirmed",
            ),
            (
                UserDecision(choice="1", rationale=None),
                DuplicateConfirmed(
                    suggestion_event_id="s2",
                    primary_transaction_id="p2",
                    duplicate_transaction_id="d2",
                    canonical_description="desc",
                    llm_was_correct=True,
                ),
                "confirmed",
            ),
            (
                UserDecision(choice="N", rationale=None),
                DuplicateRejected(
                    suggestion_event_id="s3",
                    transaction_id_1="t1",
                    transaction_id_2="t2",
                    llm_was_correct=False,
                ),
                "rejected",
            ),
        ]

        summary = service.build_summary(matches=matches, feedback=feedback)

        assert summary.user_confirmed == 2
        assert summary.user_rejected == 1
        assert summary.feedback_count == 3


class DescribeEdgeCases(DescribeDuplicateReviewService):
    """Tests for edge cases and error conditions."""

    def it_should_handle_empty_matches_list(self, service):
        """Should handle empty matches list gracefully."""
        summary = service.build_summary(matches=[], feedback=[])

        assert summary.total_matches == 0
        assert summary.llm_predicted_duplicates == 0
        assert summary.llm_predicted_not_duplicates == 0
        assert summary.feedback_count == 0

    def it_should_handle_confidence_at_boundaries(self, service, sample_pair):
        """Should handle confidence at 0.0 and 1.0."""
        matches = [
            DuplicateMatch(
                pair=sample_pair,
                assessment=DuplicateAssessment(
                    is_duplicate=True, confidence=0.0, reasoning="no confidence"
                ),
            ),
            DuplicateMatch(
                pair=sample_pair,
                assessment=DuplicateAssessment(
                    is_duplicate=True, confidence=1.0, reasoning="full confidence"
                ),
            ),
        ]

        summary = service.build_summary(matches=matches, feedback=[])

        assert summary.total_matches == 2
        assert summary.llm_predicted_duplicates == 2

    def it_should_handle_empty_rationale(
        self, service, mock_event_store, sample_pair, sample_assessment
    ):
        """Should handle empty/None rationale in user decision."""
        decision = UserDecision(choice="1", rationale=None)

        event, _ = service.process_user_decision(
            decision=decision,
            pair=sample_pair,
            assessment=sample_assessment,
            suggestion_id="s1",
        )

        assert event.user_rationale is None


class DescribeDuplicateValidation(DescribeDuplicateReviewService):
    """Tests for validate_duplicate_pair method."""

    def _txn(self, txn_id: str, account_id: str, amount: float, is_duplicate: int = 0) -> dict:
        return {
            "transaction_id": txn_id,
            "account_id": account_id,
            "amount": amount,
            "is_duplicate": is_duplicate,
        }

    def it_should_reject_when_primary_is_already_duplicate(self, service):
        """Should return is_valid=False when the primary is already marked as a duplicate."""
        primary = self._txn("txn001", "MYBANK_CHQ", -50.0, is_duplicate=1)
        duplicate = self._txn("txn002", "MYBANK_CHQ", -50.0)

        result = service.validate_duplicate_pair(primary, duplicate)

        assert not result.is_valid
        assert any("already marked as a duplicate" in e for e in result.errors)

    def it_should_warn_when_duplicate_is_already_marked(self, service):
        """Should include a warning when the duplicate transaction is already marked."""
        primary = self._txn("txn001", "MYBANK_CHQ", -50.0)
        duplicate = self._txn("txn002", "MYBANK_CHQ", -50.0, is_duplicate=1)

        result = service.validate_duplicate_pair(primary, duplicate)

        assert result.is_valid
        assert any("already marked" in w for w in result.warnings)

    def it_should_warn_about_cross_account_duplicates(self, service):
        """Should warn when the two transactions are from different accounts."""
        primary = self._txn("txn001", "MYBANK_CHQ", -50.0)
        duplicate = self._txn("txn002", "MYBANK_CC", -50.0)

        result = service.validate_duplicate_pair(primary, duplicate)

        assert result.is_valid
        assert any("different account" in w for w in result.warnings)

    def it_should_warn_about_amount_mismatch_above_threshold(self, service):
        """Should warn when amounts differ by more than 0.01."""
        primary = self._txn("txn001", "MYBANK_CHQ", -50.00)
        duplicate = self._txn("txn002", "MYBANK_CHQ", -50.50)

        result = service.validate_duplicate_pair(primary, duplicate)

        assert result.is_valid
        assert any("different amount" in w for w in result.warnings)

    def it_should_pass_valid_same_account_same_amount_pair(self, service):
        """Should return is_valid=True with no errors or warnings for a clean pair."""
        primary = self._txn("txn001", "MYBANK_CHQ", -50.00)
        duplicate = self._txn("txn002", "MYBANK_CHQ", -50.00)

        result = service.validate_duplicate_pair(primary, duplicate)

        assert result.is_valid
        assert result.errors == []
        assert result.warnings == []


class DescribeDuplicateFiltering(DescribeDuplicateReviewService):
    """Tests for filter_by_confidence and exclude_already_processed methods."""

    def _make_match(self, confidence: float, is_duplicate: bool = True) -> DuplicateMatch:
        pair = TransactionPair(
            txn1_id=f"txn1_{confidence}",
            txn1_date=date(2025, 1, 1),
            txn1_description="EXAMPLE UTILITY",
            txn1_amount=-50.0,
            txn1_account="MYBANK_CHQ",
            txn2_id=f"txn2_{confidence}",
            txn2_date=date(2025, 1, 1),
            txn2_description="EXAMPLE UTILITY",
            txn2_amount=-50.0,
            txn2_account="MYBANK_CHQ",
        )
        assessment = DuplicateAssessment(
            is_duplicate=is_duplicate, confidence=confidence, reasoning="test"
        )
        return DuplicateMatch(pair=pair, assessment=assessment)

    def it_should_filter_matches_below_confidence_threshold(self, service):
        """Should return only matches with confidence >= min_confidence."""
        matches = [
            self._make_match(0.3),
            self._make_match(0.7),
            self._make_match(0.9),
        ]

        filtered = service.filter_by_confidence(matches, min_confidence=0.7)

        assert len(filtered) == 2
        assert all(m.assessment.confidence >= 0.7 for m in filtered)

    def it_should_exclude_pairs_where_either_is_already_duplicate(self, service, sample_pair):
        """Should skip pairs where either transaction is already marked as duplicate."""
        # Projection builder mock: txn1 is a duplicate, txn2 is not
        mock_projection_builder = MagicMock()

        def get_transaction(txn_id):
            if txn_id == sample_pair.txn1_id:
                return {"transaction_id": txn_id, "is_duplicate": 1}
            return {"transaction_id": txn_id, "is_duplicate": 0}

        mock_projection_builder.get_transaction.side_effect = get_transaction

        match = DuplicateMatch(
            pair=sample_pair,
            assessment=DuplicateAssessment(is_duplicate=True, confidence=0.9, reasoning="test"),
        )

        filtered, skipped = service.exclude_already_processed([match], mock_projection_builder)

        assert len(filtered) == 0
        assert skipped == 1

    def it_should_return_skipped_count(self, service, sample_pair):
        """Should return the number of pairs that were skipped."""
        mock_projection_builder = MagicMock()
        mock_projection_builder.get_transaction.return_value = {"is_duplicate": 0}

        match = DuplicateMatch(
            pair=sample_pair,
            assessment=DuplicateAssessment(is_duplicate=True, confidence=0.9, reasoning="test"),
        )

        filtered, skipped = service.exclude_already_processed([match], mock_projection_builder)

        assert len(filtered) == 1
        assert skipped == 0


class DescribeMarkManualDuplicate(DescribeDuplicateReviewService):
    """Tests for mark_manual_duplicate method."""

    def it_should_create_manual_duplicate_event(
        self, service, mock_event_store
    ):
        """Should create DuplicateConfirmed event with manual sentinel values."""
        event = service.mark_manual_duplicate(
            primary_transaction_id="abc123def456",
            duplicate_transaction_id="xyz789uvw012",
            canonical_description="SPOTIFY PREMIUM",
        )

        assert isinstance(event, DuplicateConfirmed)
        assert event.primary_transaction_id == "abc123def456"
        assert event.duplicate_transaction_id == "xyz789uvw012"
        assert event.canonical_description == "SPOTIFY PREMIUM"
        assert event.suggestion_event_id == "manual"
        assert event.user_rationale == "Manual duplicate marking"
        assert event.llm_was_correct is False

    def it_should_append_event_to_store(
        self, service, mock_event_store
    ):
        """Should append the DuplicateConfirmed event to the event store."""
        service.mark_manual_duplicate(
            primary_transaction_id="abc123def456",
            duplicate_transaction_id="xyz789uvw012",
            canonical_description="SPOTIFY PREMIUM",
        )

        mock_event_store.append_event.assert_called_once()
        event = mock_event_store.append_event.call_args[0][0]
        assert isinstance(event, DuplicateConfirmed)
        assert event.primary_transaction_id == "abc123def456"
