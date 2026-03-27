"""Infer categorization rules from transaction history."""

from __future__ import annotations

import json

from rich.table import Table

from gilt.services.event_sourcing_service import EventSourcingService
from gilt.services.rule_inference_service import RuleInferenceService
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

from .util import console, fmt_amount_str, print_dry_run_message, require_projections


def _display_rules(rules):
    table = Table(title="Inferred Categorization Rules", show_lines=False)
    table.add_column("Description", style="white")
    table.add_column("Category", style="green")
    table.add_column("Evidence", style="cyan", justify="right")
    table.add_column("Confidence", style="blue", justify="right")

    for rule in rules:
        cat_display = rule.category
        if rule.subcategory:
            cat_display = f"{rule.category}:{rule.subcategory}"
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
    table = Table(title="Transactions Matching Rules", show_lines=False)
    table.add_column("TxnID", style="dim", no_wrap=True)
    table.add_column("Date", style="dim")
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("Inferred Category", style="green")
    table.add_column("Evidence", style="blue", justify="right")

    for m in matches:
        txn = m.transaction
        cat_display = m.rule.category
        if m.rule.subcategory:
            cat_display = f"{m.rule.category}:{m.rule.subcategory}"
        table.add_row(
            txn["transaction_id"][:8],
            txn.get("transaction_date", ""),
            txn.get("account_id", ""),
            (txn.get("canonical_description") or "")[:50],
            fmt_amount_str(txn.get("amount", 0)),
            cat_display,
            f"{m.rule.evidence_count}/{m.rule.total_count}",
        )

    console.print("\n")
    console.print(table)


def _write_matches(matches, workspace, event_store, projection_builder):
    """Apply rule-based categorizations: emit events, update CSVs, rebuild projections."""
    from gilt.services.categorization_persistence_service import (
        CategorizationPersistenceService,
        CategorizationUpdate,
    )

    persistence_svc = CategorizationPersistenceService(
        event_store=event_store,
        projection_builder=projection_builder,
        ledger_data_dir=workspace.ledger_data_dir,
    )
    updates = [
        CategorizationUpdate(
            transaction_id=m.transaction["transaction_id"],
            account_id=m.transaction.get("account_id", ""),
            category=m.rule.category,
            subcategory=m.rule.subcategory,
            source="rule",
            confidence=m.rule.confidence,
        )
        for m in matches
    ]
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
    es_service = EventSourcingService(workspace=workspace)
    event_store = es_service.get_event_store()
    projection_builder = es_service.get_projection_builder()

    _write_matches(matches, workspace, event_store, projection_builder)
    return 0


__all__ = ["run"]
