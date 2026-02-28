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


from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.prompt import Prompt
from rich.table import Table

from gilt.config import DEFAULT_OLLAMA_MODEL
from gilt.services.duplicate_review_service import (
    DuplicateReviewService,
    UserDecision,
)
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.transfer.duplicate_detector import DuplicateDetector
from gilt.workspace import Workspace


def _setup_event_sourcing(console, workspace):
    """Initialize event sourcing and ensure projections are current. Returns (es, store, builder) or exit code."""
    data_dir = workspace.ledger_data_dir
    if not data_dir.exists():
        console.print(f"[red]Error:[/red] Data directory not found: {data_dir}")
        return 1

    es_service = EventSourcingService(workspace=workspace)
    event_store_status = es_service.check_event_store_status(data_dir=data_dir)
    if not event_store_status.exists:
        if event_store_status.csv_files_count and event_store_status.csv_files_count > 0:
            console.print(
                f"[yellow]Event store not found, but found "
                f"{event_store_status.csv_files_count} CSV file(s)[/]"
            )
            console.print()
            console.print("[bold]To migrate your existing data to event sourcing:[/]")
            console.print("  gilt migrate-to-events --write")
            console.print()
            console.print("[dim]This will create the event store and projections from your CSV files.[/dim]")
        else:
            console.print(f"[red]Error:[/red] No data found in {data_dir}")
            console.print()
            console.print("[bold]To get started:[/]")
            console.print("  1. Export CSV files from your bank")
            console.print("  2. Place them in ingest/ directory")
            console.print("  3. Run: gilt ingest --write")
        return 1

    event_store = es_service.get_event_store()
    projection_builder = es_service.get_projection_builder()

    projection_status = es_service.check_projection_status(event_store)
    if not projection_status.exists:
        console.print("[yellow]Projections not found, rebuilding from events...[/]")
        events_processed = projection_builder.rebuild_from_scratch(event_store)
        console.print(f"[green]✓[/green] Rebuilt projections ({events_processed} events processed)")
        console.print()
    elif projection_status.is_outdated:
        console.print(
            f"[yellow]Projections outdated (event {projection_status.current_sequence}/"
            f"{projection_status.latest_event_sequence}), rebuilding...[/]"
        )
        events_processed = projection_builder.rebuild_incremental(event_store)
        console.print(f"[green]✓[/green] Processed {events_processed} new event(s)")
        console.print()

    return es_service, event_store, projection_builder


def _analyze_candidates(console, detector, candidates, detection_method):
    """Analyze candidate pairs with progress bar. Returns sorted matches."""
    console.print(f"[yellow]Analyzing {len(candidates)} candidates with {detection_method}...[/yellow]")

    matches = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Assessing duplicates...", total=len(candidates))
        for pair in candidates:
            assessment = detector.assess_duplicate(pair)
            from gilt.model.duplicate import DuplicateMatch
            matches.append(DuplicateMatch(pair=pair, assessment=assessment))
            progress.update(task, advance=1)

    matches.sort(key=lambda m: m.assessment.confidence, reverse=True)
    return matches


def _display_and_review_match(
    console, i, total, match, review_service, detector, projection_builder, event_store,
    suggestion_event_id, feedback,
):
    """Display a single match and handle interactive review. Returns updated feedback list."""
    pair = match.pair
    assessment = match.assessment

    table = Table(
        title=f"Match {i}/{total} - Confidence: {match.confidence_pct:.1f}%",
        show_header=True, show_lines=True,
    )
    table.add_column("Field", style="cyan")
    table.add_column("Latest (1)", style="magenta")
    table.add_column("Original (2)", style="yellow")

    table.add_row("ID", pair.txn2_id[:8], pair.txn1_id[:8])
    table.add_row("Date", str(pair.txn2_date), str(pair.txn1_date))
    table.add_row("Account", pair.txn2_account, pair.txn1_account)
    table.add_row("Amount", f"{pair.txn2_amount:.2f}", f"{pair.txn1_amount:.2f}")
    table.add_row("Description", pair.txn2_description, pair.txn1_description)

    if hasattr(pair, "txn1_source_file") and hasattr(pair, "txn2_source_file"):
        src1 = pair.txn1_source_file or "[dim]unknown[/dim]"
        src2 = pair.txn2_source_file or "[dim]unknown[/dim]"
        table.add_row("Source File", src2, src1)

    console.print(table)
    console.print(f"[dim]LLM Reasoning:[/dim] {assessment.reasoning}")
    console.print()

    smart_default = review_service.calculate_smart_default(detector.learned_patterns)
    console.print("[yellow]Are these duplicates?[/yellow]")
    hint1 = smart_default.hint if smart_default.default_choice == "1" else ""
    hint2 = smart_default.hint if smart_default.default_choice == "2" else ""
    console.print(f"  1) Yes, use latest description (bank's current format){hint1}")
    console.print(f"  2) Yes, use original description{hint2}")
    console.print("  N) No, these are separate transactions")
    console.print()

    choice = Prompt.ask("Choice [1/2/N]", choices=["1", "2", "n", "N"], default=smart_default.default_choice, show_choices=False)
    rationale = Prompt.ask("Rationale (optional)", default="")

    decision = UserDecision(choice=choice, rationale=rationale if rationale else None)
    event, action = review_service.process_user_decision(
        decision=decision, pair=pair, assessment=assessment, suggestion_id=suggestion_event_id,
    )
    feedback.append((decision, event, action))

    if action == "confirmed":
        from gilt.model.events import DuplicateConfirmed
        assert isinstance(event, DuplicateConfirmed)
        console.print(f"[green]✓ Duplicate confirmed (using: {event.canonical_description})[/green]")
    else:
        console.print("[green]✓ Rejection recorded[/green]")

    events_processed = projection_builder.rebuild_incremental(event_store)
    if events_processed > 0:
        console.print("[dim]✓ Projection updated[/dim]")
    console.print()

    if detector.prompt_manager:
        detector.prompt_manager.add_feedback(
            pair=pair, llm_said_duplicate=assessment.is_duplicate,
            llm_confidence=assessment.confidence,
            user_confirmed=(choice.upper() != "N"), llm_reasoning=assessment.reasoning,
        )


def _display_summary(console, filtered_matches, feedback, use_llm, detector, interactive, review_service):
    """Display final summary."""
    summary = review_service.build_summary(matches=filtered_matches, feedback=feedback)

    console.print()
    console.print("[cyan]Summary:[/cyan]")
    console.print(f"  Total matches analyzed: {summary.total_matches}")

    method_name = "ML" if (not use_llm and detector._ml_classifier) else "LLM"
    console.print(f"  {method_name} predicted duplicates: {summary.llm_predicted_duplicates}")
    console.print(f"  {method_name} predicted not duplicates: {summary.llm_predicted_not_duplicates}")

    if interactive and summary.feedback_count > 0:
        console.print()
        console.print("[cyan]Interactive Session:[/cyan]")
        console.print(f"  Reviewed: {summary.feedback_count}")
        console.print(f"  Confirmed as duplicates: {summary.user_confirmed}")
        console.print(f"  Rejected as not duplicates: {summary.user_rejected}")
        console.print(f"  Events emitted: {summary.user_confirmed + summary.user_rejected}")

        if detector.prompt_manager:
            stats = detector.prompt_manager.get_stats()
            if stats["total_feedback"] > 0:
                console.print()
                console.print("[cyan]Overall Learning Stats:[/cyan]")
                console.print(f"  Total feedback collected: {stats['total_feedback']}")
                console.print(f"  Current accuracy: {stats['accuracy']:.1%}")
                console.print(f"  True positives: {stats['true_positives']}")
                console.print(f"  False positives: {stats['false_positives']}")
                console.print(f"  True negatives: {stats['true_negatives']}")
                console.print(f"  False negatives: {stats['false_negatives']}")


def _print_detection_info(
    console, data_dir, detection_method, use_llm, model, detector,
    max_days_apart, amount_tolerance, interactive,
):
    """Print detection configuration banner."""
    console.print(f"[cyan]Scanning for duplicates in:[/cyan] {data_dir}")
    console.print(f"[dim]Detection method:[/dim] {detection_method}")

    if use_llm or not detector._ml_classifier:
        console.print(f"[dim]LLM model:[/dim] {model}")
        console.print(f"[dim]Prompt version:[/dim] {detector.prompt_version}")
        if detector.learned_patterns:
            console.print(f"[dim]Learned patterns:[/dim] {len(detector.learned_patterns)} patterns loaded")
    else:
        console.print("[dim]ML model:[/dim] Trained on user feedback")
    console.print(f"[dim]Max days apart:[/dim] {max_days_apart}")
    console.print(f"[dim]Amount tolerance:[/dim] {amount_tolerance}")
    if interactive:
        console.print("[yellow]Interactive mode:[/yellow] enabled (will emit events for your decisions)")
    console.print()


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
    console = Console()
    data_dir = workspace.ledger_data_dir

    setup_result = _setup_event_sourcing(console, workspace)
    if isinstance(setup_result, int):
        return setup_result
    es_service, event_store, projection_builder = setup_result

    review_service = DuplicateReviewService(event_store=event_store)

    detector = DuplicateDetector(
        model=model, data_dir=data_dir if interactive else None,
        event_store_path=workspace.event_store_path, use_ml=not use_llm,
    )

    detection_method = "LLM" if use_llm else ("ML" if detector._ml_classifier else "LLM (fallback)")
    _print_detection_info(
        console, data_dir, detection_method, use_llm, model, detector,
        max_days_apart, amount_tolerance, interactive,
    )

    console.print("[yellow]Loading transactions from projections...[/yellow]")
    transactions = detector.load_all_transactions(data_dir)
    console.print(f"[green]Loaded {len(transactions)} transactions[/green]")

    console.print("[yellow]Finding candidate pairs...[/yellow]")
    candidates = detector.find_potential_duplicates(
        transactions, max_days_apart=max_days_apart, amount_tolerance=amount_tolerance,
    )
    console.print(f"[green]Found {len(candidates)} candidate pairs[/green]")

    if not candidates:
        console.print("[green]No potential duplicates found![/green]")
        return 0

    matches = _analyze_candidates(console, detector, candidates, detection_method)
    console.print()

    filtered_matches = [m for m in matches if m.assessment.confidence >= min_confidence]
    if not filtered_matches:
        console.print(f"[green]No duplicates found with confidence >= {min_confidence:.0%}[/green]")
        return 0

    console.print(
        f"[cyan]Found {len(filtered_matches)} potential duplicate(s) "
        f"with confidence >= {min_confidence:.0%}:[/cyan]"
    )
    console.print()

    feedback = []
    skipped_count = 0

    for i, match in enumerate(filtered_matches, 1):
        pair = match.pair

        txn1 = projection_builder.get_transaction(pair.txn1_id)
        txn2 = projection_builder.get_transaction(pair.txn2_id)
        if (txn1 and txn1.get("is_duplicate", 0) == 1) or (txn2 and txn2.get("is_duplicate", 0) == 1):
            skipped_count += 1
            continue

        _, event_id = review_service.create_suggestion_event(
            pair=pair, assessment=match.assessment, model=model, prompt_version=detector.prompt_version,
        )

        if not interactive:
            # Display non-interactive match info
            console.print(f"[bold]Match {i}/{len(filtered_matches)}[/] - Confidence: {match.confidence_pct:.1f}%")
            console.print(f"  {pair.txn2_id[:8]} vs {pair.txn1_id[:8]}: {pair.txn2_description}")
            console.print(f"  [dim]{match.assessment.reasoning}[/dim]")
            console.print()
        else:
            try:
                _display_and_review_match(
                    console, i, len(filtered_matches), match, review_service, detector,
                    projection_builder, event_store, event_id, feedback,
                )
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted by user[/yellow]")
                break

    if detector.prompt_manager:
        detector.prompt_manager._save_prompt()
        console.print("[dim]✓ Feedback saved to prompt manager[/dim]")

    if skipped_count > 0:
        console.print()
        console.print(f"[dim]Skipped {skipped_count} pair(s) already processed in this session[/dim]")

    _display_summary(console, filtered_matches, feedback, use_llm, detector, interactive, review_service)

    return 0


__all__ = ["run"]
