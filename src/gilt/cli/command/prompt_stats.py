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


from gilt.model.events import PromptUpdated
from gilt.transfer.prompt_learning import PromptLearningService
from gilt.workspace import Workspace

from ..console import console
from ..event_sourcing_bootstrap import require_event_sourcing
from .prompt_stats_view import (
    display_accuracy_metrics,
    display_learned_patterns,
    display_prompt_history,
)


def _generate_and_emit_update(
    learning_service: PromptLearningService, event_store
) -> None:
    """Generate a prompt update from learned patterns and emit it to the event store."""
    console.print("[yellow]Generating prompt update...[/yellow]")

    prompt_events = event_store.get_events_by_type("PromptUpdated")
    current_version = "v1"
    if prompt_events:
        latest_prompt = prompt_events[-1]
        if isinstance(latest_prompt, PromptUpdated):
            current_version = latest_prompt.prompt_version

    prompt_update = learning_service.build_prompt_update(current_version)

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
    ready = require_event_sourcing(workspace)
    event_store = ready.event_store
    learning_service = PromptLearningService(event_store)

    console.print("[cyan]Prompt Learning Statistics[/cyan]")
    console.print()

    metrics = learning_service.get_accuracy()

    if metrics.total_feedback == 0:
        console.print("[yellow]No feedback data available yet.[/yellow]")
        console.print("[dim]Run 'gilt duplicates --interactive' to provide feedback.[/dim]")
        return 0

    display_accuracy_metrics(console, metrics)

    patterns = learning_service.identify_learned_patterns()
    display_learned_patterns(console, patterns)

    if generate_update:
        _generate_and_emit_update(learning_service, event_store)

    display_prompt_history(console, event_store)

    return 0


__all__ = ["run"]
