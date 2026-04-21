"""Infer categorization rules from transaction history."""

from __future__ import annotations

import json

from rich.table import Table

from gilt.model.category_io import format_category_path
from gilt.services.categorization_persistence_service import (
    categorization_updates_from_rule_matches,
)
from gilt.services.rule_inference_service import RuleInferenceService
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

from .util import (
    console,
    display_transaction_matches,
    fmt_amount_str,
    print_dry_run_message,
    require_event_sourcing,
    require_persistence_service,
    require_projections,
)


def _display_rules(rules):
    table = Table(title="Inferred Categorization Rules", show_lines=False)
    table.add_column("Description", style="white")
    table.add_column("Category", style="green")
    table.add_column("Evidence", style="cyan", justify="right")
    table.add_column("Confidence", style="blue", justify="right")

    for rule in rules:
        cat_display = format_category_path(rule.category, rule.subcategory)
        table.add_row(
            rule.description[:60],
            cat_display,
            f"{rule.evidence_count}/{rule.total_count}",
            f"{rule.confidence:.0%}",
        )

    console.print("\n")
    console.print(table)
    console.print(f"\n[dim]{len(rules)} rule(s) inferred[/dim]")


def _display_matches(matches):
    def row_fn(m) -> tuple:
        txn = m.transaction
        cat_display = format_category_path(m.rule.category, m.rule.subcategory)
        return (
            txn.get("account_id", ""),
            txn["transaction_id"][:8],
            txn.get("transaction_date", ""),
            (txn.get("canonical_description") or "")[:50],
            fmt_amount_str(txn.get("amount", 0)),
            cat_display,
            f"{m.rule.evidence_count}/{m.rule.total_count}",
        )

    console.print("\n")
    display_transaction_matches(
        "Transactions Matching Rules",
        [
            ("Inferred Category", {"style": "green"}),
            ("Evidence", {"style": "blue", "justify": "right"}),
        ],
        matches,
        row_fn,
    )


def _write_matches(matches, workspace, event_store, projection_builder):
    """Apply rule-based categorizations: emit events, update CSVs, rebuild projections."""
    persistence_svc = require_persistence_service(event_store, projection_builder, workspace)
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
    projection_builder_check = require_projections(workspace)
    if projection_builder_check is None:
        return 1

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
        _display_rules(rules)
        return 0

    # Apply mode: find uncategorized transactions matching rules
    all_txns = ProjectionBuilder(workspace.projections_path).get_all_transactions(
        include_duplicates=False
    )
    matches = service.apply_rules(all_txns, rules)

    if not matches:
        console.print("[green]No uncategorized transactions match inferred rules[/green]")
        return 0

    _display_matches(matches)

    if not write:
        print_dry_run_message(detail=f"{len(matches)} transaction(s)")
        return 0

    # Write mode
    ready = require_event_sourcing(workspace)
    if ready is None:
        return 1

    _write_matches(matches, workspace, ready.event_store, ready.projection_builder)
    return 0


__all__ = ["run"]
