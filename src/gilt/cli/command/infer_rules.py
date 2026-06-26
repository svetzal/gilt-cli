"""Infer categorization rules from transaction history."""

from __future__ import annotations

import json

from gilt.services.categorization_persistence_service import (
    categorization_updates_from_rule_matches,
)
from gilt.services.rule_inference_service import RuleInferenceService
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

from ..console import console, print_dry_run_message
from ..event_sourcing_bootstrap import (
    require_event_sourcing,
    require_persistence_service,
    require_projections,
)
from .infer_rules_view import display_matches, display_rules


def _write_matches(matches, ready, workspace):
    """Apply rule-based categorizations: emit events, update CSVs, rebuild projections."""
    persistence_svc = require_persistence_service(ready, workspace)
    updates = categorization_updates_from_rule_matches(matches)
    console.print("[dim]Updating projections...[/dim]")
    persistence_svc.persist_categorizations(updates)
    console.print(f"[green]Categorized {len(matches)} transaction(s) via rules[/green]")


def run(
    *,
    workspace: Workspace,
    apply: bool = False,
    write: bool = False,
    min_evidence: int = 3,
    min_confidence: float = 0.9,
    export: str | None = None,
) -> int:
    """Infer and optionally apply categorization rules from history."""
    require_projections(workspace)
    service = RuleInferenceService(workspace.projections_path)
    rules = service.infer_rules(min_evidence=min_evidence, min_confidence=min_confidence)

    if not rules:
        console.print("[yellow]No rules could be inferred with current thresholds[/yellow]")
        console.print("[dim]Try lowering --min-evidence or --min-confidence[/dim]")
        return 0

    if export:
        export_data = [
            {
                "description": r.description,
                "category": r.category,
                "subcategory": r.subcategory,
                "evidence_count": r.evidence_count,
                "total_count": r.total_count,
                "confidence": r.confidence,
            }
            for r in rules
        ]
        from pathlib import Path

        Path(export).write_text(json.dumps(export_data, indent=2), encoding="utf-8")
        console.print(f"[green]Exported {len(rules)} rules to {export}[/green]")
        return 0

    if not apply:
        display_rules(rules)
        return 0

    return _run_apply_mode(workspace, service, rules, write)


def _run_apply_mode(workspace: Workspace, service: RuleInferenceService, rules, write: bool) -> int:
    """Find uncategorized transactions matching rules, display, and optionally persist."""
    all_txns = ProjectionBuilder(workspace.projections_path).get_all_transactions(
        include_duplicates=False
    )
    matches = service.run_rules(all_txns, rules)

    if not matches:
        console.print("[green]No uncategorized transactions match inferred rules[/green]")
        return 0

    display_matches(matches)

    if not write:
        print_dry_run_message(detail=f"{len(matches)} transaction(s)")
        return 0

    ready = require_event_sourcing(workspace)
    _write_matches(matches, ready, workspace)
    return 0


__all__ = ["run"]
