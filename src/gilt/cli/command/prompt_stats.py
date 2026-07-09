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
    display_update_generated,
    print_generating_update,
    print_no_feedback,
    print_no_patterns_learned,
    print_statistics_header,
)


def _build_and_emit_update(
    learning_service: PromptLearningService, event_store
) -> None:
    """Generate a prompt update from learned patterns and emit it to the event store."""
    print_generating_update()

    prompt_events = event_store.get_events_by_type("PromptUpdated")
    current_version = "v1"
    if prompt_events:
        latest_prompt = prompt_events[-1]
        if isinstance(latest_prompt, PromptUpdated):
            current_version = latest_prompt.prompt_version

    prompt_update = learning_service.build_prompt_update(current_version)

    if prompt_update:
        event_store.append_event(prompt_update)
        display_update_generated(prompt_update)
    else:
        print_no_patterns_learned()


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

    print_statistics_header()

    metrics = learning_service.get_accuracy()

    if metrics.total_feedback == 0:
        print_no_feedback()
        return 0

    display_accuracy_metrics(console, metrics)

    patterns = learning_service.identify_learned_patterns()
    display_learned_patterns(console, patterns)

    if generate_update:
        _build_and_emit_update(learning_service, event_store)

    display_prompt_history(console, event_store)

    return 0


__all__ = ["run"]
