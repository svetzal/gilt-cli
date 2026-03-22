from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from gilt.model.events import (
    DuplicateConfirmed,
    DuplicateRejected,
    DuplicateSuggested,
)
from gilt.storage.event_store import EventStore
from gilt.transfer.prompt_learning import AccuracyMetrics, PromptLearningService


def _append_suggestion(
    event_store: EventStore,
    is_duplicate: bool,
    txn1_id: str = "txn001",
    txn2_id: str = "txn002",
    txn2_description: str = "SAMPLE STORE",
    reasoning: str = "Similar transaction",
) -> str:
    event = DuplicateSuggested(
        transaction_id_1=txn1_id,
        transaction_id_2=txn2_id,
        confidence=0.9 if is_duplicate else 0.2,
        reasoning=reasoning,
        model="llama3",
        prompt_version="v1",
        assessment={
            "is_duplicate": is_duplicate,
            "txn2_description": txn2_description,
        },
    )
    event_store.append_event(event)
    return event.event_id


def _append_confirmation(
    event_store: EventStore,
    suggestion_event_id: str,
    canonical_description: str = "SAMPLE STORE",
) -> None:
    event = DuplicateConfirmed(
        suggestion_event_id=suggestion_event_id,
        primary_transaction_id="txn001",
        duplicate_transaction_id="txn002",
        canonical_description=canonical_description,
        llm_was_correct=True,
    )
    event_store.append_event(event)


def _append_rejection(
    event_store: EventStore,
    suggestion_event_id: str,
    user_rationale: str = "",
) -> None:
    event = DuplicateRejected(
        suggestion_event_id=suggestion_event_id,
        transaction_id_1="txn001",
        transaction_id_2="txn002",
        user_rationale=user_rationale,
        llm_was_correct=False,
    )
    event_store.append_event(event)


class DescribeAccuracyMetrics:
    def it_should_calculate_precision_as_tp_over_tp_plus_fp(self):
        metrics = AccuracyMetrics(
            total_feedback=4,
            true_positives=3,
            false_positives=1,
            true_negatives=0,
            false_negatives=0,
            accuracy=0.75,
        )
        assert metrics.precision == pytest.approx(0.75)

    def it_should_return_zero_precision_when_no_positives(self):
        metrics = AccuracyMetrics(
            total_feedback=0,
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0,
            accuracy=0.0,
        )
        assert metrics.precision == 0.0

    def it_should_calculate_recall_as_tp_over_tp_plus_fn(self):
        metrics = AccuracyMetrics(
            total_feedback=4,
            true_positives=3,
            false_positives=1,
            true_negatives=0,
            false_negatives=1,
            accuracy=0.75,
        )
        assert metrics.recall == pytest.approx(0.75)

    def it_should_return_zero_recall_when_no_tp_or_fn(self):
        metrics = AccuracyMetrics(
            total_feedback=0,
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0,
            accuracy=0.0,
        )
        assert metrics.recall == 0.0

    def it_should_calculate_f1_as_harmonic_mean(self):
        # precision = 3/4 = 0.75, recall = 3/4 = 0.75
        # f1 = 2 * 0.75 * 0.75 / (0.75 + 0.75) = 0.75
        metrics = AccuracyMetrics(
            total_feedback=8,
            true_positives=3,
            false_positives=1,
            true_negatives=3,
            false_negatives=1,
            accuracy=0.75,
        )
        assert metrics.f1_score == pytest.approx(0.75)

    def it_should_return_zero_f1_when_precision_and_recall_are_zero(self):
        metrics = AccuracyMetrics(
            total_feedback=0,
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0,
            accuracy=0.0,
        )
        assert metrics.f1_score == 0.0


class DescribePromptLearningServiceAccuracy:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def event_store(self, temp_dir):
        return EventStore(str(temp_dir / "events.db"))

    @pytest.fixture
    def service(self, event_store):
        return PromptLearningService(event_store)

    def it_should_return_zero_metrics_with_no_events(self, service):
        metrics = service.calculate_accuracy()
        assert metrics.total_feedback == 0
        assert metrics.true_positives == 0
        assert metrics.false_positives == 0
        assert metrics.true_negatives == 0
        assert metrics.false_negatives == 0
        assert metrics.accuracy == 0.0

    def it_should_count_true_positive_when_llm_said_duplicate_and_user_confirmed(
        self, service, event_store
    ):
        suggestion_id = _append_suggestion(event_store, is_duplicate=True)
        _append_confirmation(event_store, suggestion_id)
        metrics = service.calculate_accuracy()
        assert metrics.true_positives == 1
        assert metrics.false_positives == 0

    def it_should_count_false_positive_when_llm_said_duplicate_and_user_rejected(
        self, service, event_store
    ):
        suggestion_id = _append_suggestion(event_store, is_duplicate=True)
        _append_rejection(event_store, suggestion_id)
        metrics = service.calculate_accuracy()
        assert metrics.false_positives == 1
        assert metrics.true_positives == 0

    def it_should_count_true_negative_when_llm_said_not_duplicate_and_user_rejected(
        self, service, event_store
    ):
        suggestion_id = _append_suggestion(event_store, is_duplicate=False)
        _append_rejection(event_store, suggestion_id)
        metrics = service.calculate_accuracy()
        assert metrics.true_negatives == 1

    def it_should_count_false_negative_when_llm_said_not_duplicate_and_user_confirmed(
        self, service, event_store
    ):
        suggestion_id = _append_suggestion(event_store, is_duplicate=False)
        _append_confirmation(event_store, suggestion_id)
        metrics = service.calculate_accuracy()
        assert metrics.false_negatives == 1

    def it_should_handle_mixed_feedback_correctly(self, service, event_store):
        tp_id = _append_suggestion(event_store, is_duplicate=True, txn1_id="a", txn2_id="b")
        _append_confirmation(event_store, tp_id)

        fp_id = _append_suggestion(event_store, is_duplicate=True, txn1_id="c", txn2_id="d")
        _append_rejection(event_store, fp_id)

        tn_id = _append_suggestion(event_store, is_duplicate=False, txn1_id="e", txn2_id="f")
        _append_rejection(event_store, tn_id)

        fn_id = _append_suggestion(event_store, is_duplicate=False, txn1_id="g", txn2_id="h")
        _append_confirmation(event_store, fn_id)

        metrics = service.calculate_accuracy()
        assert metrics.true_positives == 1
        assert metrics.false_positives == 1
        assert metrics.true_negatives == 1
        assert metrics.false_negatives == 1
        assert metrics.total_feedback == 4
        assert metrics.accuracy == pytest.approx(0.5)

    def it_should_ignore_orphaned_confirmations_without_matching_suggestion(
        self, service, event_store
    ):
        event = DuplicateConfirmed(
            suggestion_event_id="nonexistent-id",
            primary_transaction_id="txn001",
            duplicate_transaction_id="txn002",
            canonical_description="SAMPLE STORE",
            llm_was_correct=True,
        )
        event_store.append_event(event)
        metrics = service.calculate_accuracy()
        assert metrics.total_feedback == 0


class DescribePromptLearningServiceDescriptionPreferences:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def event_store(self, temp_dir):
        return EventStore(str(temp_dir / "events.db"))

    @pytest.fixture
    def service(self, event_store):
        return PromptLearningService(event_store)

    def it_should_return_zero_confidence_with_no_confirmations(self, service):
        pattern = service.analyze_description_preferences()
        assert pattern.confidence == 0.0
        assert pattern.evidence_count == 0

    def it_should_detect_preference_for_latest_description(self, service, event_store):
        for i in range(3):
            sid = _append_suggestion(
                event_store,
                is_duplicate=True,
                txn1_id=f"old{i}",
                txn2_id=f"new{i}",
                txn2_description="SAMPLE STORE UPDATED",
            )
            _append_confirmation(event_store, sid, canonical_description="SAMPLE STORE UPDATED")

        pattern = service.analyze_description_preferences()
        assert "latest" in pattern.description.lower()
        assert pattern.evidence_count == 3

    def it_should_detect_preference_for_original_description(self, service, event_store):
        for i in range(3):
            sid = _append_suggestion(
                event_store,
                is_duplicate=True,
                txn1_id=f"old{i}",
                txn2_id=f"new{i}",
                txn2_description="SAMPLE STORE UPDATED",
            )
            _append_confirmation(event_store, sid, canonical_description="ORIGINAL DESCRIPTION")

        pattern = service.analyze_description_preferences()
        assert "original" in pattern.description.lower()

    def it_should_report_no_strong_preference_when_balanced(self, service, event_store):
        for i in range(2):
            sid = _append_suggestion(
                event_store,
                is_duplicate=True,
                txn1_id=f"old{i}",
                txn2_id=f"new{i}",
                txn2_description="SAMPLE STORE UPDATED",
            )
            _append_confirmation(event_store, sid, canonical_description="SAMPLE STORE UPDATED")

        for i in range(2, 4):
            sid = _append_suggestion(
                event_store,
                is_duplicate=True,
                txn1_id=f"old{i}",
                txn2_id=f"new{i}",
                txn2_description="SAMPLE STORE UPDATED",
            )
            _append_confirmation(event_store, sid, canonical_description="ORIGINAL DESCRIPTION")

        pattern = service.analyze_description_preferences()
        assert "no strong preference" in pattern.description.lower()

    def it_should_skip_orphaned_confirmations_without_matching_suggestion(
        self, service, event_store
    ):
        event = DuplicateConfirmed(
            suggestion_event_id="no-such-id",
            primary_transaction_id="txn001",
            duplicate_transaction_id="txn002",
            canonical_description="SAMPLE STORE",
            llm_was_correct=True,
        )
        event_store.append_event(event)
        pattern = service.analyze_description_preferences()
        assert pattern.evidence_count == 0


class DescribePromptLearningServicePatternIdentification:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def event_store(self, temp_dir):
        return EventStore(str(temp_dir / "events.db"))

    @pytest.fixture
    def service(self, event_store):
        return PromptLearningService(event_store)

    def it_should_detect_location_based_false_positive_pattern(self, service, event_store):
        sid = _append_suggestion(event_store, is_duplicate=True)
        _append_rejection(event_store, sid, user_rationale="different location")
        patterns = service._analyze_false_positives()
        assert len(patterns) == 1
        assert patterns[0].pattern_type == "false_positive"
        assert "location" in patterns[0].description.lower()

    def it_should_return_empty_when_no_rejections(self, service):
        patterns = service._analyze_false_positives()
        assert patterns == []

    def it_should_return_true_positive_pattern_when_three_or_more_confirmations(
        self, service, event_store
    ):
        for i in range(3):
            sid = _append_suggestion(
                event_store, is_duplicate=True, txn1_id=f"a{i}", txn2_id=f"b{i}"
            )
            _append_confirmation(event_store, sid)
        patterns = service._analyze_true_positives()
        assert len(patterns) == 1
        assert patterns[0].pattern_type == "true_positive"

    def it_should_not_return_true_positive_pattern_with_fewer_than_three(
        self, service, event_store
    ):
        for i in range(2):
            sid = _append_suggestion(
                event_store, is_duplicate=True, txn1_id=f"a{i}", txn2_id=f"b{i}"
            )
            _append_confirmation(event_store, sid)
        patterns = service._analyze_true_positives()
        assert patterns == []


class DescribePromptLearningServicePromptGeneration:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def event_store(self, temp_dir):
        return EventStore(str(temp_dir / "events.db"))

    @pytest.fixture
    def service(self, event_store):
        return PromptLearningService(event_store)

    def it_should_return_none_when_no_patterns_learned(self, service):
        result = service.generate_prompt_update()
        assert result is None

    def it_should_generate_prompt_updated_event_with_learned_patterns(self, service, event_store):
        for i in range(3):
            sid = _append_suggestion(
                event_store, is_duplicate=True, txn1_id=f"a{i}", txn2_id=f"b{i}"
            )
            _append_confirmation(event_store, sid)

        result = service.generate_prompt_update(current_version="v1")
        assert result is not None
        assert result.prompt_version == "v2"
        assert result.previous_version == "v1"
        assert len(result.learned_patterns) > 0
        assert "accuracy" in result.accuracy_metrics

    def it_should_increment_version_correctly(self, service, event_store):
        for i in range(3):
            sid = _append_suggestion(
                event_store, is_duplicate=True, txn1_id=f"a{i}", txn2_id=f"b{i}"
            )
            _append_confirmation(event_store, sid)

        result = service.generate_prompt_update(current_version="v3")
        assert result.prompt_version == "v4"

    def it_should_default_to_v2_on_unparseable_version(self, service, event_store):
        for i in range(3):
            sid = _append_suggestion(
                event_store, is_duplicate=True, txn1_id=f"a{i}", txn2_id=f"b{i}"
            )
            _append_confirmation(event_store, sid)

        result = service.generate_prompt_update(current_version="invalid")
        assert result.prompt_version == "v2"
