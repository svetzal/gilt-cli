from __future__ import annotations

"""
Prompt learning service for analyzing user feedback on duplicate detection.

This service analyzes DuplicateConfirmed and DuplicateRejected events to:
- Calculate LLM accuracy metrics
- Identify patterns in user decisions
- Generate PromptUpdated events with learned insights
- Track description preferences (latest vs original)

Privacy:
- All analysis happens locally on event store
- No external network calls
"""

from dataclasses import dataclass

from gilt.model.events import (
    DuplicateConfirmed,
    DuplicateRejected,
    DuplicateSuggested,
    PromptUpdated,
)
from gilt.storage.event_store import EventStore


@dataclass
class AccuracyMetrics:
    """Accuracy metrics for duplicate detection."""

    total_feedback: int
    true_positives: int  # LLM said duplicate, user confirmed
    false_positives: int  # LLM said duplicate, user rejected
    true_negatives: int  # LLM said not duplicate, user confirmed
    false_negatives: int  # LLM said not duplicate, user said it is
    accuracy: float  # (TP + TN) / total

    @property
    def precision(self) -> float:
        """Precision: TP / (TP + FP)."""
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        """Recall: TP / (TP + FN)."""
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)

    @property
    def f1_score(self) -> float:
        """F1 score: harmonic mean of precision and recall."""
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)


@dataclass
class LearnedPattern:
    """A pattern learned from user feedback."""

    pattern_type: str  # "description_preference", "false_positive", "true_positive"
    description: str  # Natural language description
    confidence: float  # How confident we are in this pattern (0-1)
    evidence_count: int  # Number of examples supporting this pattern


class PromptLearningService:
    """Service for analyzing user feedback and generating learned patterns."""

    def __init__(self, event_store: EventStore):
        """Initialize learning service.

        Args:
            event_store: Event store containing duplicate detection events
        """
        self.event_store = event_store

    def calculate_accuracy(self) -> AccuracyMetrics:
        """Calculate accuracy metrics from all feedback events.

        Returns:
            Accuracy metrics including TP, FP, TN, FN, and overall accuracy
        """
        suggestions = self._get_all_suggestions()
        confirmations = self._get_all_confirmations()
        rejections = self._get_all_rejections()

        # Build map of suggestion_id -> assessment
        suggestion_map = {s.event_id: s for s in suggestions}

        tp = 0  # LLM said duplicate, user confirmed
        fp = 0  # LLM said duplicate, user rejected
        tn = 0  # LLM said not duplicate, user rejected (agreed)
        fn = 0  # LLM said not duplicate, user confirmed (disagreed)

        # Process confirmations
        for conf in confirmations:
            if conf.suggestion_event_id in suggestion_map:
                suggestion = suggestion_map[conf.suggestion_event_id]
                if suggestion.assessment.get("is_duplicate", False):
                    tp += 1
                else:
                    fn += 1  # LLM missed it, user found it

        # Process rejections
        for rej in rejections:
            if rej.suggestion_event_id in suggestion_map:
                suggestion = suggestion_map[rej.suggestion_event_id]
                if suggestion.assessment.get("is_duplicate", False):
                    fp += 1  # LLM wrong, user corrected
                else:
                    tn += 1  # LLM correct, user agreed not duplicate

        total = tp + fp + tn + fn
        accuracy = (tp + tn) / total if total > 0 else 0.0

        return AccuracyMetrics(
            total_feedback=total,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            accuracy=accuracy,
        )

    def analyze_description_preferences(self) -> LearnedPattern:
        """Analyze which description format users prefer.

        Returns:
            Pattern describing user's description preferences
        """
        confirmations = self._get_all_confirmations()
        suggestions = self._get_all_suggestions()

        if not confirmations:
            return LearnedPattern(
                pattern_type="description_preference",
                description="Insufficient data to determine description preference",
                confidence=0.0,
                evidence_count=0,
            )

        # Build map for quick lookup
        suggestion_map = {s.event_id: s for s in suggestions}

        latest_count = 0
        original_count = 0

        for conf in confirmations:
            if conf.suggestion_event_id not in suggestion_map:
                continue

            suggestion = suggestion_map[conf.suggestion_event_id]

            # Check if canonical description matches txn2 (latest) or txn1 (original)
            # This is a heuristic - we assume txn2 is usually "latest" based on event order
            if conf.canonical_description == suggestion.assessment.get("txn2_description"):
                latest_count += 1
            else:
                original_count += 1

        total = latest_count + original_count
        if total == 0:
            return LearnedPattern(
                pattern_type="description_preference",
                description="No description preference data available",
                confidence=0.0,
                evidence_count=0,
            )

        latest_pct = (latest_count / total) * 100
        confidence = abs(latest_count - original_count) / total  # Confidence = how skewed

        if latest_pct > 60:
            description = f"User prefers latest description format {latest_pct:.0f}% of the time ({latest_count}/{total} cases)"
        elif latest_pct < 40:
            description = f"User prefers original description format {100 - latest_pct:.0f}% of the time ({original_count}/{total} cases)"
        else:
            description = f"User has no strong preference (latest: {latest_pct:.0f}%, original: {100 - latest_pct:.0f}%)"

        return LearnedPattern(
            pattern_type="description_preference",
            description=description,
            confidence=confidence,
            evidence_count=total,
        )

    def identify_learned_patterns(self) -> list[LearnedPattern]:
        """Identify all learned patterns from feedback history.

        Returns:
            List of learned patterns with descriptions and confidence
        """
        patterns = []

        # Description preference pattern
        desc_pattern = self.analyze_description_preferences()
        if desc_pattern.evidence_count > 0:
            patterns.append(desc_pattern)

        # False positive patterns (LLM said duplicate, user rejected)
        fp_patterns = self._analyze_false_positives()
        patterns.extend(fp_patterns)

        # True positive patterns (good duplicate detections)
        tp_patterns = self._analyze_true_positives()
        patterns.extend(tp_patterns)

        return patterns

    def generate_prompt_update(self, current_version: str = "v1") -> PromptUpdated | None:
        """Generate a PromptUpdated event if enough learning has occurred.

        Args:
            current_version: Current prompt version

        Returns:
            PromptUpdated event if patterns were learned, None otherwise
        """
        patterns = self.identify_learned_patterns()
        if not patterns:
            return None

        metrics = self.calculate_accuracy()

        # Determine next version
        try:
            version_num = int(current_version.lstrip("v"))
            next_version = f"v{version_num + 1}"
        except (ValueError, AttributeError):
            next_version = "v2"

        learned_pattern_strings = [
            f"{p.pattern_type}: {p.description} (confidence: {p.confidence:.2f}, evidence: {p.evidence_count})"
            for p in patterns
        ]

        return PromptUpdated(
            prompt_version=next_version,
            previous_version=current_version,
            learned_patterns=learned_pattern_strings,
            accuracy_metrics={
                "total_feedback": metrics.total_feedback,
                "accuracy": metrics.accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
                "true_positives": metrics.true_positives,
                "false_positives": metrics.false_positives,
                "true_negatives": metrics.true_negatives,
                "false_negatives": metrics.false_negatives,
            },
        )

    def _get_all_suggestions(self) -> list[DuplicateSuggested]:
        """Get all DuplicateSuggested events."""
        events = self.event_store.get_events_by_type("DuplicateSuggested")
        return [e for e in events if isinstance(e, DuplicateSuggested)]

    def _get_all_confirmations(self) -> list[DuplicateConfirmed]:
        """Get all DuplicateConfirmed events."""
        events = self.event_store.get_events_by_type("DuplicateConfirmed")
        return [e for e in events if isinstance(e, DuplicateConfirmed)]

    def _get_all_rejections(self) -> list[DuplicateRejected]:
        """Get all DuplicateRejected events."""
        events = self.event_store.get_events_by_type("DuplicateRejected")
        return [e for e in events if isinstance(e, DuplicateRejected)]

    def _analyze_false_positives(self) -> list[LearnedPattern]:
        """Analyze false positives to identify common mistakes.

        Returns:
            List of patterns describing common false positives
        """
        patterns = []

        rejections = self._get_all_rejections()
        suggestions = self._get_all_suggestions()

        if not rejections:
            return patterns

        suggestion_map = {s.event_id: s for s in suggestions}

        # Look for location-based false positives
        location_fps = []
        for rej in rejections:
            if rej.suggestion_event_id not in suggestion_map:
                continue

            suggestion = suggestion_map[rej.suggestion_event_id]
            if not suggestion.assessment.get("is_duplicate", False):
                continue  # Only interested in cases where LLM said duplicate but was wrong

            _reasoning = suggestion.reasoning.lower()
            rationale = (rej.user_rationale or "").lower()

            if "location" in rationale or "city" in rationale or "different" in rationale:
                location_fps.append((suggestion, rej))

        if location_fps:
            patterns.append(
                LearnedPattern(
                    pattern_type="false_positive",
                    description=f"Avoid marking as duplicates when transactions have different locations/cities - found {len(location_fps)} cases",
                    confidence=min(0.9, len(location_fps) / max(len(rejections), 1)),
                    evidence_count=len(location_fps),
                )
            )

        return patterns

    def _analyze_true_positives(self) -> list[LearnedPattern]:
        """Analyze true positives to reinforce good patterns.

        Returns:
            List of patterns describing good duplicate detections
        """
        patterns = []

        confirmations = self._get_all_confirmations()
        if len(confirmations) >= 3:
            patterns.append(
                LearnedPattern(
                    pattern_type="true_positive",
                    description=f"Successfully detected {len(confirmations)} duplicates - continuing to use same-day, same-amount, same-account heuristic",
                    confidence=0.8,
                    evidence_count=len(confirmations),
                )
            )

        return patterns


__all__ = ["PromptLearningService", "AccuracyMetrics", "LearnedPattern"]
