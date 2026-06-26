"""Rich rendering functions for the prompt-stats command."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def display_accuracy_metrics(console: Console, metrics) -> None:
    """Build and print the accuracy metrics table."""
    metrics_table = Table(title="Accuracy Metrics", show_header=True)
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="green", justify="right")

    metrics_table.add_row("Total Feedback", str(metrics.total_feedback))
    metrics_table.add_row("Overall Accuracy", f"{metrics.accuracy:.1%}")
    metrics_table.add_row("Precision", f"{metrics.precision:.1%}")
    metrics_table.add_row("Recall", f"{metrics.recall:.1%}")
    metrics_table.add_row("F1 Score", f"{metrics.f1_score:.1%}")
    metrics_table.add_row("", "")
    metrics_table.add_row("True Positives", str(metrics.true_positives))
    metrics_table.add_row("False Positives", str(metrics.false_positives))
    metrics_table.add_row("True Negatives", str(metrics.true_negatives))
    metrics_table.add_row("False Negatives", str(metrics.false_negatives))

    console.print(metrics_table)
    console.print()


def display_learned_patterns(console: Console, patterns: list) -> None:
    """Print a panel for each learned pattern."""
    if not patterns:
        return

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


def display_prompt_history(console: Console, event_store) -> None:
    """Display prompt version history table."""
    from gilt.model.events import PromptUpdated

    prompt_events = event_store.get_events_by_type("PromptUpdated")
    if not prompt_events:
        return

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
