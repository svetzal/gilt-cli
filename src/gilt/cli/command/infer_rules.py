"""Infer categorization rules from transaction history."""

from __future__ import annotations

import json

from gilt.services.categorization_persistence_service import (
    categorization_updates_from_rule_matches,
)
from gilt.services.rule_inference_service import RuleInferenceService
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

from .. import mutations
from ..event_sourcing_bootstrap import (
    require_event_sourcing,
    require_persistence_service,
    require_projections,
)
from .infer_rules_view import (
    display_matches,
    display_rules,
    print_categorized,
    print_exported,
    print_no_matches,
    print_no_rules,
    print_updating_projections,
)


def _write_matches(matches, ready, workspace):
    """Apply rule-based categorizations: emit events, update CSVs, rebuild projections."""
    persistence_svc = require_persistence_service(ready, workspace)
    updates = categorization_updates_from_rule_matches(matches)
    print_updating_projections()
    persistence_svc.persist_categorizations(updates)
    print_categorized(len(matches))


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
        print_no_rules()
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
        print_exported(len(rules), export)
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
        print_no_matches()
        return 0

    def apply() -> int:
        ready = require_event_sourcing(workspace)
        _write_matches(matches, ready, workspace)
        return 0

    return mutations.run_confirmed_mutation(
        matches=matches,
        display=lambda: display_matches(matches),
        confirm_prompt="",
        assume_yes=True,
        write=write,
        apply=apply,
    )


__all__ = ["run"]
