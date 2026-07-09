from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from gilt.ingest import load_accounts_config, normalize_file
from gilt.model.ledger_repository import LEDGER_IO_ERRORS, LedgerRepository
from gilt.services.ingestion_orchestration_service import IngestionOrchestrationService
from gilt.services.ingestion_service import IngestionService
from gilt.workspace import Workspace

if TYPE_CHECKING:
    from gilt.storage.event_store import EventStore

from .. import mutations
from ..console import print_error
from ..event_sourcing_bootstrap import build_event_sourcing_service
from .ingest_view import (
    display_plan,
    display_post_counts,
    display_pre_counts,
    print_auto_categorized,
    print_done,
    print_event_store,
    print_event_store_total,
    print_no_transfers,
    print_processed,
    print_projection_total,
    print_skip,
    print_transfer_metadata,
    print_wrote,
)


@dataclass
class NormalizationResult:
    name: str
    status: str
    out_path: Path | None


def _load_ledger_counts(paths: Iterable[Path]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for lp in paths:
        repo = LedgerRepository(lp.parent)
        try:
            groups = repo.load(lp.stem)
            counts[lp.name] = len(groups)
        except LEDGER_IO_ERRORS:
            counts[lp.name] = 0
    return counts


def _perform_normalization(
    plan: Iterable[tuple[Path, str | None]],
    output_dir: Path,
    ingestion_service: IngestionService,
    event_store: EventStore | None = None,
) -> tuple[list[NormalizationResult], int, int]:
    """Normalize files. Returns (results, written, skipped)."""
    written = 0
    skipped = 0
    results: list[NormalizationResult] = []
    for p, acct_id in plan:
        if not acct_id:
            results.append(NormalizationResult(name=p.name, status="skip", out_path=None))
            skipped += 1
            continue
        try:
            out_path = normalize_file(
                p,
                acct_id,
                output_dir,
                event_store=event_store,
                amount_sign=ingestion_service.amount_sign_for(acct_id),
            )
            results.append(NormalizationResult(name=p.name, status="ok", out_path=out_path))
            written += 1
        except LEDGER_IO_ERRORS as e:
            print_error(f"Failed to normalize {p.name}: {e}")
            results.append(NormalizationResult(name=p.name, status="error", out_path=None))
            skipped += 1
    return results, written, skipped


def _run_post_ingest(workspace, output_dir, event_store, es_service):
    """Link transfers, rebuild projections, auto-categorize. Returns the result object."""
    orch = IngestionOrchestrationService(workspace)
    return orch.run_post_ingest(output_dir, event_store, es_service)


def run(
    *,
    workspace: Workspace,
    write: bool = False,
) -> int:
    """Ingest and normalize raw CSVs into standardized per-account ledgers.

    Dry-run by default (write=False). Returns an exit code.
    """
    ingestion_service = IngestionService(accounts=load_accounts_config(workspace.accounts_config))
    ingestion_plan = ingestion_service.build_ingestion_plan(workspace.ingest_dir)

    return mutations.run_confirmed_mutation(
        matches=list(ingestion_plan.files),
        display=lambda: display_plan(ingestion_plan.files, ingestion_plan.total_files),
        confirm_prompt="",
        assume_yes=True,
        write=write,
        apply=lambda: _run_ingest(workspace, ingestion_service, ingestion_plan),
    )


def _run_ingest(workspace: Workspace, ingestion_service, ingestion_plan) -> int:
    """Perform the full ingest: normalize files, rebuild projections, report results."""
    output_dir = workspace.ledger_data_dir
    es_service = build_event_sourcing_service(workspace)
    event_store = es_service.get_event_store()
    print_event_store(es_service.event_store_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_paths = ingestion_service.discover_ledger_paths(output_dir)

    pre_counts = _load_ledger_counts(ledger_paths)
    display_pre_counts(pre_counts)

    norm_results, written, skipped = _perform_normalization(
        ingestion_plan.files, output_dir, ingestion_service, event_store=event_store
    )
    for nr in norm_results:
        if nr.status == "skip":
            print_skip(nr.name)
        elif nr.status == "ok":
            print_wrote(nr.out_path)

    post_counts = _load_ledger_counts(ledger_paths)
    display_post_counts(post_counts, pre_counts)

    result = _run_post_ingest(workspace, output_dir, event_store, es_service)
    if result.modified_transfer_count:
        print_transfer_metadata(result.modified_transfer_count)
    else:
        print_no_transfers()
    print_processed(result.events_processed)
    print_projection_total(result.total_transactions)
    if result.auto_categorized_count:
        print_auto_categorized(result.auto_categorized_count)
    print_event_store_total(result.latest_event_sequence)

    print_done(written, skipped)
    return 0
