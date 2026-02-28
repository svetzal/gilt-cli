from __future__ import annotations

"""
CLI command to show prompt learning statistics and generate prompt updates.

This command analyzes user feedback on duplicate detection and shows:
- Overall accuracy metrics
- Learned patterns
- Description preferences
- Historical prompt versions

Can also generate new PromptUpdated events when sufficient learning has occurred.

Privacy:
- All analysis happens locally on event store
- No external network calls
"""


from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from gilt.model.events import PromptUpdated
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.transfer.prompt_learning import PromptLearningService
from gilt.workspace import Workspace


def run(
    workspace: Workspace,
    generate_update: bool = False,
) -> int:
    """Show prompt learning statistics and optionally generate updates.

    Args:
        workspace: Workspace for resolving data paths
        generate_update: Whether to generate a PromptUpdated event

    Returns:
        Exit code (0 = success)
    """
    console = Console()
    data_dir = workspace.ledger_data_dir

    if not data_dir.exists():
        console.print(f"[red]Error:[/red] Data directory not found: {data_dir}")
        return 1

    # Initialize event sourcing service
    es_service = EventSourcingService(workspace=workspace)

    # Check if event store exists
    event_store_status = es_service.check_event_store_status(data_dir=data_dir)
    if not event_store_status.exists:
        console.print(f"[red]Error:[/red] Event store not found: {es_service.event_store_path}")
        console.print(
            "[yellow]Hint:[/yellow] Run 'gilt ingest --write' first to create event store"
        )
        return 1

    event_store = es_service.get_event_store()
    learning_service = PromptLearningService(event_store)

    console.print("[cyan]Prompt Learning Statistics[/cyan]")
    console.print()

    # Calculate accuracy metrics
    metrics = learning_service.calculate_accuracy()

    if metrics.total_feedback == 0:
        console.print("[yellow]No feedback data available yet.[/yellow]")
        console.print("[dim]Run 'gilt duplicates --interactive' to provide feedback.[/dim]")
        return 0

    # Display accuracy metrics
    metrics_table = Table(title="Accuracy Metrics", show_header=True)
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="green", justify="right")

    metrics_table.add_row("Total Feedback", str(metrics.total_feedback))
    metrics_table.add_row("Overall Accuracy", f"{metrics.accuracy:.1%}")
    metrics_table.add_row("Precision", f"{metrics.precision:.1%}")
    metrics_table.add_row("Recall", f"{metrics.recall:.1%}")
    metrics_table.add_row("F1 Score", f"{metrics.f1_score:.1%}")
    metrics_table.add_row("", "")  # Separator
    metrics_table.add_row("True Positives", str(metrics.true_positives))
    metrics_table.add_row("False Positives", str(metrics.false_positives))
    metrics_table.add_row("True Negatives", str(metrics.true_negatives))
    metrics_table.add_row("False Negatives", str(metrics.false_negatives))

    console.print(metrics_table)
    console.print()

    # Display learned patterns
    patterns = learning_service.identify_learned_patterns()

    if patterns:
        console.print("[cyan]Learned Patterns:[/cyan]")
        console.print()

        for pattern in patterns:
            color = "green" if pattern.confidence > 0.7 else "yellow"
            panel = Panel(
                f"[bold]{pattern.description}[/bold]\n\n"
                f"Confidence: {pattern.confidence:.1%} | "
                f"Evidence: {pattern.evidence_count} cases",
                title=f"[{color}]{pattern.pattern_type.upper()}[/{color}]",
                border_style=color,
            )
            console.print(panel)
            console.print()

    # Generate prompt update if requested
    if generate_update:
        console.print("[yellow]Generating prompt update...[/yellow]")

        # Get current version from last PromptUpdated event
        prompt_events = event_store.get_events_by_type("PromptUpdated")
        current_version = "v1"
        if prompt_events:
            latest_prompt = prompt_events[-1]
            if isinstance(latest_prompt, PromptUpdated):
                current_version = latest_prompt.prompt_version

        prompt_update = learning_service.generate_prompt_update(current_version)

        if prompt_update:
            event_store.append_event(prompt_update)
            console.print(f"[green]✓ Generated {prompt_update.prompt_version}[/green]")
            console.print()
            console.print("[cyan]New patterns added:[/cyan]")
            for pattern in prompt_update.learned_patterns:
                console.print(f"  • {pattern}")
        else:
            console.print("[yellow]No new patterns learned - update not generated[/yellow]")
            console.print("[dim]More feedback needed to identify new patterns.[/dim]")

    # Show prompt version history
    prompt_events = event_store.get_events_by_type("PromptUpdated")
    if prompt_events:
        console.print()
        console.print("[cyan]Prompt Version History:[/cyan]")

        history_table = Table(show_header=True)
        history_table.add_column("Version", style="cyan")
        history_table.add_column("Accuracy", style="green", justify="right")
        history_table.add_column("Patterns Learned", style="yellow", justify="right")
        history_table.add_column("Timestamp", style="dim")

        for event in prompt_events:
            if not isinstance(event, PromptUpdated):
                continue

            accuracy = event.accuracy_metrics.get("accuracy", 0.0)
            patterns_count = len(event.learned_patterns)
            timestamp = event.event_timestamp.strftime("%Y-%m-%d %H:%M")

            history_table.add_row(
                event.prompt_version,
                f"{accuracy:.1%}",
                str(patterns_count),
                timestamp,
            )

        console.print(history_table)

    return 0


__all__ = ["run"]
