"""Rich rendering functions for the duplicates command.

All functions in this module perform console output only — no user prompts,
no business logic, no persistence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..console import console

if TYPE_CHECKING:
    pass


def display_match_options(console_obj, smart_default) -> None:
    """Print the duplicate-review choice options."""
    hint1 = smart_default.hint if smart_default.default_choice == "1" else ""
    hint2 = smart_default.hint if smart_default.default_choice == "2" else ""
    console_obj.print("[yellow]Are these duplicates?[/yellow]")
    console_obj.print(f"  1) Yes, use latest description (bank's current format){hint1}")
    console_obj.print(f"  2) Yes, use original description{hint2}")
    console_obj.print("  N) No, these are separate transactions")
    console_obj.print()


def display_non_interactive_results(filtered_matches) -> None:
    """Print each match in non-interactive mode."""
    for i, match in enumerate(filtered_matches, 1):
        pair = match.pair
        console.print(
            f"[bold]Match {i}/{len(filtered_matches)}[/] - Confidence: {match.confidence_pct:.1f}%"
        )
        console.print(f"  {pair.txn2_id[:8]} vs {pair.txn1_id[:8]}: {pair.txn2_description}")
        console.print(f"  [dim]{match.assessment.reasoning}[/dim]")
        console.print()


def display_summary(
    console_obj, filtered_matches, feedback, use_llm, detector, interactive, review_service
) -> None:
    """Display final session summary."""
    summary = review_service.build_summary(matches=filtered_matches, feedback=feedback)

    console_obj.print()
    console_obj.print("[cyan]Summary:[/cyan]")
    console_obj.print(f"  Total matches analyzed: {summary.total_matches}")

    method_name = "ML" if (not use_llm and detector._ml_classifier) else "LLM"
    console_obj.print(f"  {method_name} predicted duplicates: {summary.llm_predicted_duplicates}")
    console_obj.print(
        f"  {method_name} predicted not duplicates: {summary.llm_predicted_not_duplicates}"
    )

    if interactive and summary.feedback_count > 0:
        console_obj.print()
        console_obj.print("[cyan]Interactive Session:[/cyan]")
        console_obj.print(f"  Reviewed: {summary.feedback_count}")
        console_obj.print(f"  Confirmed as duplicates: {summary.user_confirmed}")
        console_obj.print(f"  Rejected as not duplicates: {summary.user_rejected}")
        console_obj.print(f"  Events emitted: {summary.user_confirmed + summary.user_rejected}")

        if detector.prompt_manager:
            stats = detector.prompt_manager.get_stats()
            if stats["total_feedback"] > 0:
                console_obj.print()
                console_obj.print("[cyan]Overall Learning Stats:[/cyan]")
                console_obj.print(f"  Total feedback collected: {stats['total_feedback']}")
                console_obj.print(f"  Current accuracy: {stats['accuracy']:.1%}")
                console_obj.print(f"  True positives: {stats['true_positives']}")
                console_obj.print(f"  False positives: {stats['false_positives']}")
                console_obj.print(f"  True negatives: {stats['true_negatives']}")
                console_obj.print(f"  False negatives: {stats['false_negatives']}")


def print_detection_info(
    console_obj,
    data_dir,
    detection_method,
    use_llm,
    model,
    detector,
    max_days_apart,
    amount_tolerance,
    interactive,
) -> None:
    """Print detection configuration banner."""
    console_obj.print(f"[cyan]Scanning for duplicates in:[/cyan] {data_dir}")
    console_obj.print(f"[dim]Detection method:[/dim] {detection_method}")

    if use_llm or not detector._ml_classifier:
        console_obj.print(f"[dim]LLM model:[/dim] {model}")
        console_obj.print(f"[dim]Prompt version:[/dim] {detector.prompt_version}")
        if detector.learned_patterns:
            console_obj.print(
                f"[dim]Learned patterns:[/dim] {len(detector.learned_patterns)} patterns loaded"
            )
    else:
        console_obj.print("[dim]ML model:[/dim] Trained on user feedback")
    console_obj.print(f"[dim]Max days apart:[/dim] {max_days_apart}")
    console_obj.print(f"[dim]Amount tolerance:[/dim] {amount_tolerance}")
    if interactive:
        console_obj.print(
            "[yellow]Interactive mode:[/yellow] enabled (will emit events for your decisions)"
        )
    console_obj.print()


def build_analysis_progress(console_obj):
    """Build a pre-configured Rich Progress bar for candidate analysis."""
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeRemainingColumn,
    )

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console_obj,
    )


__all__ = [
    "display_match_options",
    "display_non_interactive_results",
    "display_summary",
    "print_detection_info",
    "build_analysis_progress",
]
