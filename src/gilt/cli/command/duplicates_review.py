"""Interactive review controller for the duplicates command.

Contains the user-input loop and feedback recording — purely imperative
shell for interactive duplicate review. No business logic, no rendering
beyond single-line status messages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.prompt import Prompt

from gilt.model.events import DuplicateConfirmed
from gilt.services.duplicate_review_service import UserDecision

from ..console import console

if TYPE_CHECKING:
    from .duplicates import ReviewContext


def record_feedback(ctx: ReviewContext, decision, pair, assessment, suggestion_event_id: str):
    """Apply user decision, update projections, update prompt manager.

    Returns a _FeedbackResult with action, canonical_description, and events_processed.
    """
    from .duplicates import _FeedbackResult

    event, action = ctx.review_service.run_user_decision(
        decision=decision,
        pair=pair,
        assessment=assessment,
        suggestion_id=suggestion_event_id,
    )
    ctx.feedback.append((decision, event, action))

    canonical_description = None
    if action == "confirmed":
        assert isinstance(event, DuplicateConfirmed)
        canonical_description = event.canonical_description

    events_processed = ctx.es_service.ensure_projections_up_to_date(ctx.event_store)

    if ctx.detector.prompt_manager:
        ctx.detector.prompt_manager.add_feedback(
            pair=pair,
            llm_said_duplicate=assessment.is_duplicate,
            llm_confidence=assessment.confidence,
            user_confirmed=(decision.choice.upper() != "N"),
            llm_reasoning=assessment.reasoning,
        )

    return _FeedbackResult(
        action=action,
        canonical_description=canonical_description,
        events_processed=events_processed,
    )


def display_and_review_match(
    ctx: ReviewContext, i: int, total: int, match, suggestion_event_id: str
) -> None:
    """Display a single match and handle interactive review. Appends result to ctx.feedback."""
    from gilt.cli.presentation import build_duplicate_pair_table

    from .duplicates_view import display_match_options

    pair = match.pair
    assessment = match.assessment

    # Display table
    table = build_duplicate_pair_table(
        f"Match {i}/{total} - Confidence: {match.confidence_pct:.1f}%", pair
    )
    ctx.console.print(table)
    ctx.console.print(f"[dim]LLM Reasoning:[/dim] {assessment.reasoning}")
    ctx.console.print()

    # Display options
    smart_default = ctx.review_service.get_smart_default(ctx.detector.learned_patterns)
    display_match_options(ctx.console, smart_default)

    # Prompt
    choice = Prompt.ask(
        "Choice [1/2/N]",
        choices=["1", "2", "n", "N"],
        default=smart_default.default_choice,
        show_choices=False,
    )
    rationale = Prompt.ask("Rationale (optional)", default="")
    decision = UserDecision(choice=choice, rationale=rationale if rationale else None)

    # Record feedback and display result
    fb = record_feedback(ctx, decision, pair, assessment, suggestion_event_id)
    if fb.action == "confirmed":
        ctx.console.print(
            f"[green]✓ Duplicate confirmed (using: {fb.canonical_description})[/green]"
        )
    else:
        ctx.console.print("[green]✓ Rejection recorded[/green]")
    if fb.events_processed > 0:
        ctx.console.print("[dim]✓ Projection updated[/dim]")
    ctx.console.print()


def run_review_loop(
    review_ctx: ReviewContext, filtered_matches, review_service, detector, model, interactive
) -> None:
    """Iterate over matches, emit suggestion events, run interactive review if enabled."""
    for i, match in enumerate(filtered_matches, 1):
        pair = match.pair

        _, event_id = review_service.build_suggestion_event(
            pair=pair,
            assessment=match.assessment,
            model=model,
            prompt_version=detector.prompt_version,
        )

        if interactive:
            try:
                display_and_review_match(review_ctx, i, len(filtered_matches), match, event_id)
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted by user[/yellow]")
                break


__all__ = ["record_feedback", "display_and_review_match", "run_review_loop"]
