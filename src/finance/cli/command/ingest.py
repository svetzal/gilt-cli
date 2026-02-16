from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Iterable, Tuple, Optional

from .util import console
from finance.workspace import Workspace
from finance.ingest import load_accounts_config, normalize_file
from finance.model.ledger_io import load_ledger_csv
from finance.services.ingestion_service import IngestionService
from finance.services.event_sourcing_service import EventSourcingService
from finance.transfer.linker import link_transfers


def _print_plan(plan: Iterable[Tuple[Path, str | None]], total_files: int) -> None:
    console.print("[bold]Ingestion/Normalization Plan (dry-run)[/]")
    console.print(f"Inputs matched: {total_files}")
    for p, acct_id in plan:
        console.print(f"  - {p.name} -> account_id={acct_id or 'UNKNOWN'}")
    console.print("No files were read. No outputs were written.")


def _ledger_paths_to_load(output_dir: Path, accounts) -> List[Path]:
    paths: List[Path] = []
    # Prefer configured accounts if available
    if accounts:
        for acct in accounts:
            p = output_dir / f"{acct.account_id}.csv"
            if p.exists():
                paths.append(p)
    # Also include any other *.csv present (to cover unmanaged accounts)
    for p in sorted(output_dir.glob("*.csv")):
        if p not in paths:
            paths.append(p)
    return paths


def _load_ledger_counts(paths: Iterable[Path]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for lp in paths:
        try:
            text = lp.read_text(encoding="utf-8")
            groups = load_ledger_csv(text, default_currency="CAD")
            counts[lp.name] = len(groups)
        except Exception:
            counts[lp.name] = 0
    return counts


def _perform_normalization(
    plan: Iterable[Tuple[Path, str | None]],
    output_dir: Path,
    event_store: Optional[EventStore] = None,
) -> Tuple[int, int]:
    written = 0
    skipped = 0
    for p, acct_id in plan:
        if not acct_id:
            console.print(
                f"[yellow][skip][/yellow] Could not infer account for {p.name}; "
                "update config/accounts.yml"
            )
            skipped += 1
            continue
        try:
            out_path = normalize_file(p, acct_id, output_dir, event_store=event_store)
            console.print(f"[green][ok][/green] Wrote {out_path}")
            written += 1
        except Exception as e:
            console.print(f"[red][error][/red] Failed to normalize {p.name}: {e}")
            skipped += 1
    return written, skipped


def _link_transfers_and_report(output_dir: Path) -> int:
    console.print("[bold]Linking transfers across ledgers[/]")
    modified = link_transfers(
        processed_dir=output_dir,
        window_days=3,
        epsilon_direct=0.0,
        epsilon_interac=0.0,
        fee_max_amount=3.00,
        fee_day_window=1,
        write=True,
    )
    if modified:
        console.print(
            f"[green][ok][/green] Updated {modified} ledger file(s) with transfer metadata"
        )
    else:
        console.print("[dim]No transfer links identified or no updates needed[/]")
    return modified


def run(
    *,
    workspace: Workspace,
    write: bool = False,
) -> int:
    """Ingest and normalize raw CSVs into standardized per-account ledgers.

    Dry-run by default (write=False). Returns an exit code.
    """
    config = workspace.accounts_config
    ingest_dir = workspace.ingest_dir
    output_dir = workspace.ledger_data_dir

    # Load account config (best-effort)
    accounts = load_accounts_config(config)

    # Use service to plan ingestion
    ingestion_service = IngestionService(accounts=accounts)
    ingestion_plan = ingestion_service.plan_ingestion(ingest_dir)

    if not write:
        _print_plan(ingestion_plan.files, ingestion_plan.total_files)
        return 0

    # Write mode
    # Initialize event sourcing service for dual-write pattern
    es_service = EventSourcingService(workspace=workspace)
    event_store = es_service.get_event_store()
    console.print(f"[dim]Event store: {es_service.event_store_path}[/]")

    # 1) Load existing ledgers from disk into models for all accounts (validation-only)
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_paths = _ledger_paths_to_load(output_dir, accounts)

    pre_counts = _load_ledger_counts(ledger_paths)
    if pre_counts:
        console.print("[bold]Loaded existing ledgers (pre-ingest)[/]")
        for name, cnt in sorted(pre_counts.items()):
            console.print(f"  - {name}: {cnt} transactions (groups)")

    # 2) Perform normalization/writes with event store
    written, skipped = _perform_normalization(
        ingestion_plan.files, output_dir, event_store=event_store
    )

    # 3) Reload ledgers after ingest to ensure serialization back to disk
    post_counts = _load_ledger_counts(ledger_paths)
    if post_counts:
        console.print("[bold]Reloaded ledgers (post-ingest)[/]")
        for name, cnt in sorted(post_counts.items()):
            delta = cnt - pre_counts.get(name, 0)
            sign = "+" if delta >= 0 else ""
            console.print(f"  - {name}: {cnt} groups ({sign}{delta} change)")

    # 4) Identify and mark transfers between accounts
    _link_transfers_and_report(output_dir)

    # 5) Rebuild projections to reflect new events
    console.print("[bold]Rebuilding projections from events[/]")
    projection_builder = es_service.get_projection_builder()

    # Use incremental rebuild (only new events)
    events_processed = projection_builder.rebuild_incremental(event_store)
    console.print(f"[green][ok][/green] Processed {events_processed} new event(s)")

    # Show projection stats
    transactions = projection_builder.get_all_transactions(include_duplicates=False)
    console.print(f"[dim]Projections: {len(transactions)} total transactions[/dim]")

    # Report event store stats
    latest_seq = event_store.get_latest_sequence_number()
    console.print(f"[dim]Event store: {latest_seq} events total[/]")

    console.print(f"Done. Written={written}, Skipped={skipped}")
    return 0
