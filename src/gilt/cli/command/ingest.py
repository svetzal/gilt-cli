from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from gilt.ingest import load_accounts_config, normalize_file
from gilt.model.ledger_repository import LEDGER_IO_ERRORS, LedgerRepository
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.services.ingestion_orchestration_service import IngestionOrchestrationService
from gilt.services.ingestion_service import IngestionService
from gilt.workspace import Workspace

if TYPE_CHECKING:
    from gilt.storage.event_store import EventStore

from .util import console, print_error


def _print_plan(plan: Iterable[tuple[Path, str | None]], total_files: int) -> None:
    console.print("[bold]Ingestion/Normalization Plan (dry-run)[/]")
    console.print(f"Inputs matched: {total_files}")
    for p, acct_id in plan:
        console.print(f"  - {p.name} -> account_id={acct_id or 'UNKNOWN'}")
    console.print("No files were read. No outputs were written.")


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
) -> tuple[list[tuple[str, str, Path | None]], int, int]:
    """Normalize files. Returns (results, written, skipped) where results are (name, status, out_path)."""
    written = 0
    skipped = 0
    results: list[tuple[str, str, Path | None]] = []
    for p, acct_id in plan:
        if not acct_id:
            results.append((p.name, "skip", None))
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
            results.append((p.name, "ok", out_path))
            written += 1
        except LEDGER_IO_ERRORS as e:
            print_error(f"Failed to normalize {p.name}: {e}")
            results.append((p.name, "error", None))
            skipped += 1
    return results, written, skipped


def _print_pre_counts(counts: dict[str, int]) -> None:
    if not counts:
        return
    console.print("[bold]Loaded existing ledgers (pre-ingest)[/]")
    for name, cnt in sorted(counts.items()):
        console.print(f"  - {name}: {cnt} transactions (groups)")


def _print_post_counts(counts: dict[str, int], pre_counts: dict[str, int]) -> None:
    if not counts:
        return
    console.print("[bold]Reloaded ledgers (post-ingest)[/]")
    for name, cnt in sorted(counts.items()):
        delta = cnt - pre_counts.get(name, 0)
        sign = "+" if delta >= 0 else ""
        console.print(f"  - {name}: {cnt} groups ({sign}{delta} change)")


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
    ingestion_plan = ingestion_service.plan_ingestion(workspace.ingest_dir)

    if not write:
        _print_plan(ingestion_plan.files, ingestion_plan.total_files)
        return 0

    output_dir = workspace.ledger_data_dir
    es_service = EventSourcingService(workspace=workspace)
    event_store = es_service.get_event_store()
    console.print(f"[dim]Event store: {es_service.event_store_path}[/]")

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_paths = ingestion_service.discover_ledger_paths(output_dir)

    pre_counts = _load_ledger_counts(ledger_paths)
    _print_pre_counts(pre_counts)

    norm_results, written, skipped = _perform_normalization(
        ingestion_plan.files, output_dir, ingestion_service, event_store=event_store
    )
    for name, status, out_path in norm_results:
        if status == "skip":
            console.print(
                f"[yellow][skip][/yellow] Could not infer account for {name}; "
                "update config/accounts.yml"
            )
        elif status == "ok":
            console.print(f"[green][ok][/green] Wrote {out_path}")

    post_counts = _load_ledger_counts(ledger_paths)
    _print_post_counts(post_counts, pre_counts)

    result = _run_post_ingest(workspace, output_dir, event_store, es_service)
    if result.modified_transfer_count:
        console.print(
            f"[green][ok][/green] Updated {result.modified_transfer_count} ledger file(s) with transfer metadata"
        )
    else:
        console.print("[dim]No transfer links identified or no updates needed[/]")
    console.print(f"[green][ok][/green] Processed {result.events_processed} new event(s)")
    console.print(f"[dim]Projections: {result.total_transactions} total transactions[/dim]")
    if result.auto_categorized_count:
        console.print(
            f"[green][ok][/green] Auto-categorized {result.auto_categorized_count} transaction(s) via rules"
        )
    console.print(f"[dim]Event store: {result.latest_event_sequence} events total[/]")

    console.print(f"Done. Written={written}, Skipped={skipped}")
    return 0
