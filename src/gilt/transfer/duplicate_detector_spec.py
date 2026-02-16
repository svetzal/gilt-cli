"""Tests for DuplicateDetector with adaptive prompt loading."""

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.model.duplicate import TransactionPair
from gilt.model.events import PromptUpdated
from gilt.storage.event_store import EventStore
from gilt.transfer.duplicate_detector import DuplicateDetector


class DescribeDuplicateDetectorAdaptivePrompts:
    """Test suite for adaptive prompt loading in DuplicateDetector."""

    def it_should_load_latest_prompt_updated_event(self):
        """DuplicateDetector should load the most recent PromptUpdated event."""
        with TemporaryDirectory() as tmpdir:
            event_store_path = Path(tmpdir) / "events.db"
            event_store = EventStore(str(event_store_path))

            # Create v1 prompt event
            v1_event = PromptUpdated(
                prompt_version="v1",
                previous_version=None,
                learned_patterns=["Pattern 1 from v1"],
                accuracy_metrics={
                    "total_feedback": 10,
                    "accuracy": 0.75,
                },
            )
            event_store.append_event(v1_event)

            # Create v2 prompt event (should be loaded)
            v2_event = PromptUpdated(
                prompt_version="v2",
                previous_version="v1",
                learned_patterns=[
                    "User prefers latest description format 87% of the time",
                    "Avoid marking as duplicates when different locations",
                ],
                accuracy_metrics={
                    "total_feedback": 42,
                    "accuracy": 0.881,
                },
            )
            event_store.append_event(v2_event)

            # Initialize detector with event store
            detector = DuplicateDetector(event_store_path=event_store_path)

            # Should load v2 (latest)
            assert detector.prompt_version == "v2"
            assert len(detector.learned_patterns) == 2
            assert "User prefers latest" in detector.learned_patterns[0]
            assert "different locations" in detector.learned_patterns[1]

    def it_should_use_v1_defaults_when_no_prompt_events_exist(self):
        """DuplicateDetector should default to v1 with no patterns if no
        PromptUpdated events exist.
        """
        with TemporaryDirectory() as tmpdir:
            event_store_path = Path(tmpdir) / "events.db"
            EventStore(str(event_store_path))  # Create empty event store

            detector = DuplicateDetector(event_store_path=event_store_path)

            assert detector.prompt_version == "v1"
            assert detector.learned_patterns == []

    def it_should_use_v1_defaults_when_event_store_not_found(self):
        """DuplicateDetector should gracefully default to v1 if event store doesn't exist."""
        detector = DuplicateDetector(event_store_path=Path("/nonexistent/events.db"))

        assert detector.prompt_version == "v1"
        assert detector.learned_patterns == []

    def it_should_inject_learned_patterns_into_prompt(self):
        """DuplicateDetector should inject learned patterns into the LLM prompt."""
        with TemporaryDirectory() as tmpdir:
            event_store_path = Path(tmpdir) / "events.db"
            event_store = EventStore(str(event_store_path))

            # Create prompt event with patterns
            prompt_event = PromptUpdated(
                prompt_version="v2",
                previous_version="v1",
                learned_patterns=[
                    "User prefers latest description 87% of time",
                    "Avoid different locations as duplicates",
                    "Successfully detected 33 duplicates",
                ],
                accuracy_metrics={"accuracy": 0.88},
            )
            event_store.append_event(prompt_event)

            detector = DuplicateDetector(event_store_path=event_store_path)

            # Verify patterns are loaded
            assert len(detector.learned_patterns) == 3

            # The patterns should be injected into prompts during assess_duplicate
            # We can't easily test LLM interaction, but we verify patterns are available
            assert "User prefers latest" in detector.learned_patterns[0]
            assert "different locations" in detector.learned_patterns[1]
            assert "Successfully detected" in detector.learned_patterns[2]

    def it_should_work_without_event_store_path(self):
        """DuplicateDetector should work when event_store_path is None (backward compatibility)."""
        detector = DuplicateDetector()

        assert detector.prompt_version == "v1"
        assert detector.learned_patterns == []
        assert detector.model == "qwen3:30b"

    def it_should_handle_multiple_prompt_versions_sequentially(self):
        """DuplicateDetector should correctly load the last version when multiple exist."""
        with TemporaryDirectory() as tmpdir:
            event_store_path = Path(tmpdir) / "events.db"
            event_store = EventStore(str(event_store_path))

            # Add multiple versions
            for version in ["v1", "v2", "v3", "v4"]:
                event = PromptUpdated(
                    prompt_version=version,
                    previous_version=None if version == "v1" else f"v{int(version[1])-1}",
                    learned_patterns=[f"Pattern from {version}"],
                    accuracy_metrics={"accuracy": 0.8 + int(version[1]) * 0.02},
                )
                event_store.append_event(event)

            detector = DuplicateDetector(event_store_path=event_store_path)

            # Should load v4 (most recent)
            assert detector.prompt_version == "v4"
            assert detector.learned_patterns == ["Pattern from v4"]


class DescribeTransactionPairSourceFileTracking:
    """Test suite for source_file tracking in TransactionPair."""

    def it_should_store_source_file_for_both_transactions(self):
        """TransactionPair should store source_file for both transactions."""
        pair = TransactionPair(
            txn1_id="abc123",
            txn1_date=date(2025, 1, 1),
            txn1_description="SPOTIFY",
            txn1_amount=-10.99,
            txn1_account="MYBANK_CHQ",
            txn1_source_file="2025-01-15-mybank-chequing.csv",
            txn2_id="def456",
            txn2_date=date(2025, 1, 1),
            txn2_description="SPOTIFY PREMIUM",
            txn2_amount=-10.99,
            txn2_account="MYBANK_CHQ",
            txn2_source_file="2025-02-01-mybank-chequing.csv",
        )

        assert pair.txn1_source_file == "2025-01-15-mybank-chequing.csv"
        assert pair.txn2_source_file == "2025-02-01-mybank-chequing.csv"

    def it_should_allow_none_source_files(self):
        """TransactionPair should allow None for source_file (backward compatibility)."""
        pair = TransactionPair(
            txn1_id="abc123",
            txn1_date=date(2025, 1, 1),
            txn1_description="SPOTIFY",
            txn1_amount=-10.99,
            txn1_account="MYBANK_CHQ",
            txn2_id="def456",
            txn2_date=date(2025, 1, 1),
            txn2_description="SPOTIFY PREMIUM",
            txn2_amount=-10.99,
            txn2_account="MYBANK_CHQ",
        )

        assert pair.txn1_source_file is None
        assert pair.txn2_source_file is None
