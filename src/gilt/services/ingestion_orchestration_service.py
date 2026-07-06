"""
Ingestion orchestration service - sequences the post-ingest phases.

After raw CSVs are normalized to per-account ledgers, this service:
1. Links transfers across accounts
2. Rebuilds projections from the event store
3. Applies auto-categorization via inferred rules

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt

All dependencies are injected. Returns a result summary to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from gilt.model.ledger_repository import LedgerRepository
from gilt.services.categorization_persistence_service import (
    CategorizationPersistenceService,
    categorization_updates_from_rule_matches,
)
from gilt.services.rule_inference_service import RuleInferenceService
from gilt.transfer.linker import link_transfers

if TYPE_CHECKING:
    from gilt.services.event_sourcing_service import EventSourcingService
    from gilt.storage.event_store import EventStore
    from gilt.workspace import Workspace


@dataclass
class PostIngestResult:
    """Summary of a completed post-ingest orchestration run."""

    modified_transfer_count: int
    events_processed: int
    total_transactions: int
    auto_categorized_count: int
    latest_event_sequence: int


class IngestionOrchestrationService:
    """Sequences the four post-ingest phases without emitting any console output.

    Phases:
    1. Transfer linking across ledgers
    2. Projection rebuild from event store
    3. Auto-categorization via inferred rules
    4. Result collection

    The calling CLI command is responsible for all console output.
    """

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def run_post_ingest(
        self,
        output_dir: Path,
        event_store: EventStore,
        es_service: EventSourcingService,
    ) -> PostIngestResult:
        """Run transfer linking, projection rebuild, and auto-categorization.

        Args:
            output_dir: Directory containing per-account ledger CSV files.
            event_store: Initialized event store to read/write events.
            es_service: Event sourcing service used to rebuild projections.

        Returns:
            PostIngestResult summarizing what happened in each phase.
        """
        # Phase 1: Link transfers
        modified_transfer_count = link_transfers(processed_dir=output_dir, write=True)

        # Phase 2: Rebuild projections
        projection_builder = es_service.get_projection_builder()
        events_processed = es_service.ensure_projections_up_to_date(event_store, projection_builder)

        # Phase 3: Gather transactions and apply auto-categorizations
        transactions = projection_builder.get_all_transactions(include_duplicates=False)
        matches = self._build_auto_categorizations(transactions)
        self._run_auto_categorizations(matches, event_store, projection_builder)

        # Phase 4: Collect final stats
        latest_event_sequence = event_store.get_latest_sequence_number()

        return PostIngestResult(
            modified_transfer_count=modified_transfer_count,
            events_processed=events_processed,
            total_transactions=len(transactions),
            auto_categorized_count=len(matches),
            latest_event_sequence=latest_event_sequence,
        )

    def _build_auto_categorizations(self, all_transactions: list[dict]) -> list:
        """Find uncategorized transactions matching inferred rules. No I/O side effects."""
        service = RuleInferenceService(self._workspace.projections_path)
        rules = service.infer_rules(min_evidence=3, min_confidence=0.9)
        if not rules:
            return []
        return service.run_rules(all_transactions, rules)

    def _run_auto_categorizations(
        self, matches: list, event_store: EventStore, projection_builder
    ) -> None:
        """Emit categorization events, update CSVs, and rebuild projections."""
        if not matches:
            return

        persistence_svc = CategorizationPersistenceService(
            event_store=event_store,
            projection_builder=projection_builder,
            ledger_repo=LedgerRepository(self._workspace.ledger_data_dir),
        )
        updates = categorization_updates_from_rule_matches(matches)
        persistence_svc.persist_categorizations(updates)


__all__ = ["IngestionOrchestrationService", "PostIngestResult"]
