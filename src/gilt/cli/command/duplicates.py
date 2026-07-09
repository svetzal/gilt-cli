from __future__ import annotations

"""
CLI command to detect duplicate transactions using LLM-based analysis with event sourcing.

This command scans projections for potential duplicate transactions,
using an LLM to assess whether transactions are duplicates despite variations
in description text that banks may apply over time.

When user confirms duplicates, emits DuplicateConfirmed or DuplicateRejected events.

Interactive Mode Behavior:
- Each user decision is immediately persisted as an event to the event store
- Projections are rebuilt after EACH decision (fast, incremental update)
- This enables safe interruption (Ctrl+C) without losing progress
- When resumed, already-processed duplicates won't reappear
- The candidate list for the current session stays the same (determined at startup)
  but on next run, confirmed duplicates are excluded from loading

Trade-offs:
- Pro: Events and projections always in sync, safe to interrupt anytime
- Pro: Next run shows reduced candidate count immediately
- Con: Projection rebuild adds ~0.1s per decision (acceptable for interactive use)
- Note: The current session's candidate count doesn't decrease as you work through it

Privacy:
- Uses local LLM inference (no external API calls).
- All analysis happens on local files only.
"""

# Set log level BEFORE importing mojentic modules to suppress verbose logging
import logging

logging.basicConfig(level=logging.WARNING)
logging.getLogger("mojentic").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


from dataclasses import dataclass, field

from gilt.config import DEFAULT_OLLAMA_MODEL
from gilt.model.duplicate import DuplicateMatch
from gilt.services.duplicate_review_service import DuplicateReviewService
from gilt.transfer.duplicate_detector import DuplicateDetector
from gilt.workspace import Workspace

from ..console import console
from ..event_sourcing_bootstrap import build_event_sourcing_service, require_event_sourcing
from .duplicates_review import display_and_review_match as _display_and_review_match  # noqa: F401
from .duplicates_review import record_feedback as _record_feedback  # noqa: F401
from .duplicates_review import run_review_loop as _run_review_loop
from .duplicates_view import build_analysis_progress
from .duplicates_view import display_non_interactive_results as _display_non_interactive_results
from .duplicates_view import display_summary as _display_summary
from .duplicates_view import print_analyzing as _print_analyzing
from .duplicates_view import print_candidate_count as _print_candidate_count
from .duplicates_view import print_confident_matches_header as _print_confident_matches_header
from .duplicates_view import print_detection_info as _print_detection_info
from .duplicates_view import print_feedback_saved as _print_feedback_saved
from .duplicates_view import print_loading_transactions as _print_loading_transactions
from .duplicates_view import print_no_candidates as _print_no_candidates
from .duplicates_view import print_no_confident_matches as _print_no_confident_matches
from .duplicates_view import print_skipped_pairs as _print_skipped_pairs


@dataclass
class ReviewContext:
    console: object
    review_service: object
    detector: object
    es_service: object
    event_store: object
    feedback: list = field(default_factory=list)


@dataclass
class _FeedbackResult:
    action: str
    canonical_description: str | None
    events_processed: int


def _init_detector(
    model: str,
    data_dir,
    workspace: Workspace,
    interactive: bool,
    use_llm: bool,
) -> tuple:
    """Construct a DuplicateDetector and resolve the detection method label. Returns (detector, detection_method)."""
    detector = DuplicateDetector(
        model=model,
        data_dir=data_dir if interactive else None,
        event_store_path=workspace.event_store_path,
        projections_path=workspace.projections_path,
        use_ml=not use_llm,
    )
    detection_method = "LLM" if use_llm else ("ML" if detector._ml_classifier else "LLM (fallback)")
    return detector, detection_method


def _analyze_candidates(console_obj, detector, candidates, detection_method):
    """Analyze candidate pairs with progress bar. Returns sorted matches."""
    matches = []
    with build_analysis_progress(console_obj) as progress:
        task = progress.add_task("Assessing duplicates...", total=len(candidates))
        for pair in candidates:
            assessment = detector.assess_duplicate(pair)
            matches.append(DuplicateMatch(pair=pair, assessment=assessment))
            progress.update(task, advance=1)

    matches.sort(key=lambda m: m.assessment.confidence, reverse=True)
    return matches


def _find_candidates(detector, data_dir, max_days_apart, amount_tolerance):
    """Load transactions and find candidate duplicate pairs. Returns (transactions, candidates)."""
    transactions = detector.load_all_transactions(data_dir)
    candidates = detector.find_potential_duplicates(
        transactions,
        max_days_apart=max_days_apart,
        amount_tolerance=amount_tolerance,
    )
    return transactions, candidates


def _find_matches(
    detector, review_service, candidates, detection_method, min_confidence, projection_builder
):
    """Analyze, confidence-filter, and exclude already-processed matches.

    Returns (filtered_matches, skipped_count).
    """
    matches = _analyze_candidates(console, detector, candidates, detection_method)

    filtered_matches = review_service.find_by_confidence(matches, min_confidence)
    if not filtered_matches:
        return [], 0

    filtered_matches, skipped_count = review_service.exclude_already_processed(
        filtered_matches, projection_builder
    )
    return filtered_matches, skipped_count


def _finalize_session(
    detector,
    skipped_count: int,
    filtered_matches,
    review_ctx: ReviewContext,
    use_llm: bool,
    interactive: bool,
    review_service,
) -> None:
    """Save prompt feedback, report skipped pairs, and display the session summary."""
    if detector.prompt_manager:
        detector.prompt_manager._save_prompt()
        _print_feedback_saved()

    if skipped_count > 0:
        _print_skipped_pairs(skipped_count)

    _display_summary(
        console,
        filtered_matches,
        review_ctx.feedback,
        use_llm,
        detector,
        interactive,
        review_service,
    )


def run(
    workspace: Workspace,
    model: str = DEFAULT_OLLAMA_MODEL,
    max_days_apart: int = 1,
    amount_tolerance: float = 0.001,
    min_confidence: float = 0.0,
    interactive: bool = False,
    use_llm: bool = False,
) -> int:
    """Scan projections for duplicate transactions using ML or LLM analysis with event sourcing."""
    data_dir = workspace.ledger_data_dir

    ready = require_event_sourcing(workspace)
    event_store = ready.event_store
    projection_builder = ready.projection_builder
    es_service = build_event_sourcing_service(workspace)

    review_service = DuplicateReviewService(event_store=event_store)

    detector, detection_method = _init_detector(model, data_dir, workspace, interactive, use_llm)
    _print_detection_info(
        console,
        data_dir,
        detection_method,
        use_llm,
        model,
        detector,
        max_days_apart,
        amount_tolerance,
        interactive,
    )

    _print_loading_transactions()
    _, candidates = _find_candidates(detector, data_dir, max_days_apart, amount_tolerance)
    _print_candidate_count(len(candidates))

    if not candidates:
        _print_no_candidates()
        return 0

    _print_analyzing(len(candidates), detection_method)
    filtered_matches, skipped_count = _find_matches(
        detector, review_service, candidates, detection_method, min_confidence, projection_builder
    )

    if not filtered_matches:
        _print_no_confident_matches(min_confidence)
        return 0

    _print_confident_matches_header(len(filtered_matches), min_confidence)

    review_ctx = ReviewContext(
        console=console,
        review_service=review_service,
        detector=detector,
        es_service=es_service,
        event_store=event_store,
    )

    return _run_detection_session(
        review_ctx,
        filtered_matches,
        review_service,
        detector,
        model,
        interactive,
        skipped_count,
        use_llm,
    )


def _run_detection_session(
    review_ctx: ReviewContext,
    filtered_matches: list,
    review_service,
    detector,
    model: str,
    interactive: bool,
    skipped_count: int,
    use_llm: bool,
) -> int:
    """Run review loop over matched pairs, display results, and finalize session."""
    _run_review_loop(review_ctx, filtered_matches, review_service, detector, model, interactive)

    if not interactive:
        _display_non_interactive_results(filtered_matches)

    _finalize_session(
        detector, skipped_count, filtered_matches, review_ctx, use_llm, interactive, review_service
    )
    return 0


__all__ = ["run"]
