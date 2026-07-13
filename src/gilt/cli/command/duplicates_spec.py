from __future__ import annotations

"""
Specs for the duplicates CLI command.

Focuses on _setup_event_sourcing guard logic and basic run() scenarios.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.duplicates import (
    ReviewContext,
    _analyze_candidates,
    _find_matches,
    _record_feedback,
    _run_review_loop,
    run,
)
from gilt.cli.event_sourcing_bootstrap import require_event_sourcing
from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair
from gilt.model.events import DuplicateConfirmed, DuplicateRejected, TransactionImported
from gilt.services.duplicate_review_service import UserDecision
from gilt.services.event_sourcing_service import EventSourcingReadyResult
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.testing import make_group, write_ledger
from gilt.workspace import Workspace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quiet_console() -> Console:  # noqa: F401 (kept for potential future use)
    """Create a Rich console that discards all output (for test isolation)."""
    return Console(quiet=True)


def _write_synthetic_ledger(data_dir: Path, account_id: str = "MYBANK_CHQ") -> None:
    """Write a minimal synthetic ledger CSV."""
    groups = [
        make_group(
            transaction_id="aaaa0001aaaa0001",
            date="2025-01-10",
            description="SAMPLE STORE",
            amount=-50.0,
            account_id=account_id,
        ),
    ]
    write_ledger(data_dir / f"{account_id}.csv", groups)


def _build_event_store_and_projections(ws: Workspace) -> None:
    """Populate an event store and build projections from synthetic data."""
    ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
    store = EventStore(str(ws.event_store_path))
    store.append_event(
        TransactionImported(
            transaction_id="aaaa0001aaaa0001",
            transaction_date="2025-01-10",
            source_file="mybank_export.csv",
            source_account="MYBANK_CHQ",
            raw_description="SAMPLE STORE",
            amount=Decimal("-50.00"),
            currency="CAD",
            raw_data={},
        )
    )
    builder = ProjectionBuilder(ws.projections_path)
    builder.build_from_scratch(store)


# ---------------------------------------------------------------------------
# _setup_event_sourcing guard logic
# ---------------------------------------------------------------------------


class DescribeSetupEventSourcing:
    """Specs for require_event_sourcing guard checks (formerly _setup_event_sourcing)."""

    def it_should_return_none_when_data_dir_does_not_exist(self, tmp_path):
        ws = Workspace(root=tmp_path)
        # data dir intentionally NOT created
        with pytest.raises(CommandAbort):
            require_event_sourcing(ws)

    def it_should_return_none_when_data_dir_exists_but_no_event_store_and_csvs_present(
        self, tmp_path
    ):
        ws = Workspace(root=tmp_path)
        ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
        # Put CSV file(s) but no event store
        _write_synthetic_ledger(ws.ledger_data_dir)
        # No event store created

        with pytest.raises(CommandAbort):
            require_event_sourcing(ws)

    def it_should_return_none_when_data_dir_exists_but_no_event_store_and_no_csvs(self, tmp_path):
        ws = Workspace(root=tmp_path)
        ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
        # No CSVs, no event store

        with pytest.raises(CommandAbort):
            require_event_sourcing(ws)

    def it_should_return_ready_result_when_event_store_and_projections_exist(self, tmp_path):
        ws = Workspace(root=tmp_path)
        ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
        _write_synthetic_ledger(ws.ledger_data_dir)
        _build_event_store_and_projections(ws)

        result = require_event_sourcing(ws)
        assert isinstance(result, EventSourcingReadyResult)
        assert result.ready is True
        assert result.event_store is not None
        assert result.projection_builder is not None

    def it_should_rebuild_projections_when_they_do_not_yet_exist(self, tmp_path):
        """When the event store exists but projections are missing,
        require_event_sourcing should rebuild them and return a ready result."""
        ws = Workspace(root=tmp_path)
        ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
        _write_synthetic_ledger(ws.ledger_data_dir)

        # Create event store but NOT projections
        ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
        store = EventStore(str(ws.event_store_path))
        store.append_event(
            TransactionImported(
                transaction_id="bbbb0001bbbb0001",
                transaction_date="2025-02-01",
                source_file="mybank_export.csv",
                source_account="MYBANK_CHQ",
                raw_description="ACME CORP",
                amount=Decimal("-75.00"),
                currency="CAD",
                raw_data={},
            )
        )
        # Projections deliberately NOT built

        result = require_event_sourcing(ws)
        assert isinstance(result, EventSourcingReadyResult)
        assert result.ready is True
        # Projections should now exist
        assert ws.projections_path.exists()


# ---------------------------------------------------------------------------
# run() — high-level scenarios
# ---------------------------------------------------------------------------


def _make_pair() -> TransactionPair:
    return TransactionPair(
        txn1_id="aaaa0001aaaa0001",
        txn1_description="SAMPLE STORE",
        txn1_date="2025-01-10",
        txn1_amount=-50.0,
        txn1_account="MYBANK_CHQ",
        txn2_id="bbbb0002bbbb0002",
        txn2_description="SAMPLE STORE PAYMENT",
        txn2_date="2025-01-10",
        txn2_amount=-50.0,
        txn2_account="MYBANK_CHQ",
    )


def _make_assessment(is_duplicate: bool = True, confidence: float = 0.9) -> DuplicateAssessment:
    return DuplicateAssessment(
        is_duplicate=is_duplicate,
        confidence=confidence,
        reasoning="Same amount, same date, similar description",
    )


class DescribeFilterMatches:
    """Specs for _find_matches()."""

    def it_should_find_matches_below_confidence_threshold(self):
        pair = _make_pair()
        high_conf = DuplicateMatch(pair=pair, assessment=_make_assessment(confidence=0.9))
        low_conf = DuplicateMatch(pair=pair, assessment=_make_assessment(confidence=0.2))

        detector = MagicMock()
        review_service = MagicMock()
        review_service.find_by_confidence.return_value = [high_conf]
        review_service.exclude_already_processed.return_value = ([high_conf], 0)
        projection_builder = MagicMock()

        with patch(
            "gilt.cli.command.duplicates._analyze_candidates", return_value=[high_conf, low_conf]
        ):
            result, skipped = _find_matches(
                detector, review_service, [pair], "ML", 0.5, projection_builder
            )

        assert result == [high_conf]
        assert skipped == 0

    def it_should_exclude_already_processed_pairs_from_projections(self):
        pair = _make_pair()
        match = DuplicateMatch(pair=pair, assessment=_make_assessment())

        detector = MagicMock()
        review_service = MagicMock()
        review_service.find_by_confidence.return_value = [match]
        review_service.exclude_already_processed.return_value = ([], 1)
        projection_builder = MagicMock()

        with patch("gilt.cli.command.duplicates._analyze_candidates", return_value=[match]):
            result, skipped = _find_matches(
                detector, review_service, [pair], "ML", 0.0, projection_builder
            )

        assert result == []
        assert skipped == 1

    def it_should_return_empty_list_when_no_matches_pass_filter(self):
        detector = MagicMock()
        review_service = MagicMock()
        review_service.find_by_confidence.return_value = []
        projection_builder = MagicMock()

        with patch("gilt.cli.command.duplicates._analyze_candidates", return_value=[]):
            result, skipped = _find_matches(
                detector, review_service, [], "ML", 0.9, projection_builder
            )

        assert result == []
        assert skipped == 0


class DescribeAnalyzeCandidates:
    """Specs for _analyze_candidates()."""

    def it_should_return_matches_sorted_by_confidence_descending(self):
        pair = _make_pair()
        detector = MagicMock()
        detector.assess_duplicate.side_effect = [
            _make_assessment(confidence=0.3),
            _make_assessment(confidence=0.9),
        ]

        result = _analyze_candidates(Console(quiet=True), detector, [pair, pair], "ML")

        assert result[0].assessment.confidence >= result[1].assessment.confidence

    def it_should_return_empty_list_when_detector_finds_no_matches(self):
        detector = MagicMock()

        result = _analyze_candidates(Console(quiet=True), detector, [], "ML")

        assert result == []
        detector.assess_duplicate.assert_not_called()


class DescribeRecordFeedback:
    """Specs for _record_feedback()."""

    def it_should_emit_confirmed_event_for_confirmed_choice(self):
        pair = _make_pair()
        assessment = _make_assessment()
        confirmed_event = MagicMock(spec=DuplicateConfirmed)
        confirmed_event.canonical_description = "SAMPLE STORE"

        review_service = MagicMock()
        review_service.run_user_decision.return_value = (confirmed_event, "confirmed")

        es_service = MagicMock()
        es_service.ensure_projections_up_to_date.return_value = 1

        detector = MagicMock()
        detector.prompt_manager = None

        ctx = ReviewContext(
            console=Console(quiet=True),
            review_service=review_service,
            detector=detector,
            es_service=es_service,
            event_store=MagicMock(),
        )

        decision = UserDecision(choice="1")
        result = _record_feedback(ctx, decision, pair, assessment, "evt-123")

        assert result.action == "confirmed"
        assert result.canonical_description == "SAMPLE STORE"

    def it_should_emit_rejected_event_for_rejected_choice(self):
        pair = _make_pair()
        assessment = _make_assessment()
        rejected_event = MagicMock(spec=DuplicateRejected)

        review_service = MagicMock()
        review_service.run_user_decision.return_value = (rejected_event, "rejected")

        es_service = MagicMock()
        es_service.ensure_projections_up_to_date.return_value = 0

        detector = MagicMock()
        detector.prompt_manager = None

        ctx = ReviewContext(
            console=Console(quiet=True),
            review_service=review_service,
            detector=detector,
            es_service=es_service,
            event_store=MagicMock(),
        )

        decision = UserDecision(choice="N")
        result = _record_feedback(ctx, decision, pair, assessment, "evt-456")

        assert result.action == "rejected"
        assert result.canonical_description is None

    def it_should_rebuild_projections_after_recording(self):
        pair = _make_pair()
        assessment = _make_assessment()
        confirmed_event = MagicMock(spec=DuplicateConfirmed)
        confirmed_event.canonical_description = "SAMPLE STORE"

        review_service = MagicMock()
        review_service.run_user_decision.return_value = (confirmed_event, "confirmed")

        es_service = MagicMock()
        es_service.ensure_projections_up_to_date.return_value = 5

        detector = MagicMock()
        detector.prompt_manager = None
        event_store = MagicMock()

        ctx = ReviewContext(
            console=Console(quiet=True),
            review_service=review_service,
            detector=detector,
            es_service=es_service,
            event_store=event_store,
        )

        decision = UserDecision(choice="1")
        result = _record_feedback(ctx, decision, pair, assessment, "evt-789")

        es_service.ensure_projections_up_to_date.assert_called_once_with(event_store)
        assert result.events_processed == 5


class DescribeRunReviewLoop:
    """Specs for _run_review_loop()."""

    def it_should_iterate_over_matches_calling_display_and_review(self):
        pair = _make_pair()
        match = DuplicateMatch(pair=pair, assessment=_make_assessment())
        filtered_matches = [match]

        review_service = MagicMock()
        review_service.build_suggestion_event.return_value = (MagicMock(), "evt-001")

        detector = MagicMock()
        detector.prompt_version = "v1"

        ctx = ReviewContext(
            console=Console(quiet=True),
            review_service=review_service,
            detector=detector,
            es_service=MagicMock(),
            event_store=MagicMock(),
        )

        with patch("gilt.cli.command.duplicates_review.display_and_review_match") as mock_display:
            _run_review_loop(
                ctx, filtered_matches, review_service, detector, "llama3", interactive=True
            )

        mock_display.assert_called_once()

    def it_should_handle_keyboard_interrupt_gracefully(self):
        pair = _make_pair()
        match = DuplicateMatch(pair=pair, assessment=_make_assessment())
        filtered_matches = [match, match]

        review_service = MagicMock()
        review_service.build_suggestion_event.return_value = (MagicMock(), "evt-001")

        detector = MagicMock()
        detector.prompt_version = "v1"

        ctx = ReviewContext(
            console=Console(quiet=True),
            review_service=review_service,
            detector=detector,
            es_service=MagicMock(),
            event_store=MagicMock(),
        )

        with patch(
            "gilt.cli.command.duplicates_review.display_and_review_match",
            side_effect=KeyboardInterrupt,
        ):
            _run_review_loop(
                ctx, filtered_matches, review_service, detector, "llama3", interactive=True
            )


class DescribeDuplicatesRun:
    """Specs for the duplicates run() function."""

    def it_should_return_1_when_data_dir_does_not_exist(self, tmp_path):
        ws = Workspace(root=tmp_path)
        # Data dir intentionally absent

        with pytest.raises(CommandAbort) as exc_info:
            run(workspace=ws)
        assert exc_info.value.code == 1

    def it_should_return_0_when_no_candidate_pairs_found(self, tmp_path):
        """With a single unique transaction there are no duplicates to detect."""
        ws = Workspace(root=tmp_path)
        ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
        _write_synthetic_ledger(ws.ledger_data_dir)
        _build_event_store_and_projections(ws)

        result = run(workspace=ws)
        assert result == 0

    def it_should_display_matches_without_prompting_in_non_interactive_mode(self, tmp_path):
        """In non-interactive mode, matches are displayed without user prompts."""
        ws = Workspace(root=tmp_path)
        ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
        _build_event_store_and_projections(ws)

        pair = _make_pair()
        match = DuplicateMatch(pair=pair, assessment=_make_assessment())
        ready = MagicMock()
        ready.event_store = MagicMock()
        ready.projection_builder = MagicMock()

        with (
            patch("gilt.cli.command.duplicates.require_event_sourcing", return_value=ready),
            patch("gilt.cli.command.duplicates._find_candidates", return_value=([], [pair])),
            patch("gilt.cli.command.duplicates._find_matches", return_value=([match], 0)),
            patch("gilt.cli.command.duplicates._run_review_loop"),
            patch("gilt.cli.command.duplicates._display_summary"),
            patch("gilt.cli.command.duplicates.build_event_sourcing_service"),
            patch("gilt.cli.command.duplicates.DuplicateReviewService"),
            patch("gilt.cli.command.duplicates._init_detector") as mock_init,
            patch("gilt.cli.command.duplicates._print_detection_info"),
        ):
            mock_detector = MagicMock()
            mock_detector.prompt_manager = None
            mock_init.return_value = (mock_detector, "ML")

            result = run(workspace=ws, interactive=False)

        assert result == 0
