from __future__ import annotations

"""
Reingest command — purge and re-ingest transactions for a single account.

Removes the account's ledger CSV, purges related events and projections,
clears cached intelligence, then re-runs ingestion for that account only.
"""

from pathlib import Path

from gilt.ingest import load_accounts_config, normalize_file
from gilt.model.ledger_repository import LEDGER_IO_ERRORS
from gilt.services.ingestion_service import IngestionService
from gilt.services.reingestion_service import ReingestionService
from gilt.transfer.linker import link_transfers
from gilt.workspace import Workspace

from .util import console, print_dry_run_message, print_error, require_event_sourcing


def _delete_existing_ledger(ledger_path: Path) -> bool:
    """Delete the ledger CSV if it exists. Returns True if it existed."""
    if ledger_path.exists():
        ledger_path.unlink()
        return True
    return False


def _reingest_source_files(
    account_files: list[tuple],
    ingestion_service: IngestionService,
    account: str,
    output_dir: Path,
    event_store: object,
) -> tuple[int, list[str], list[Path]]:
    """Normalize each source file. Returns (written_count, errors, written_paths)."""
    amount_sign = ingestion_service.amount_sign_for(account)
    written = 0
    errors: list[str] = []
    written_paths: list[Path] = []
    for p, acct_id in account_files:
        try:
            out_path = normalize_file(
                p,
                acct_id,
                output_dir,
                event_store=event_store,
                amount_sign=amount_sign,
            )
            written_paths.append(out_path)
            written += 1
        except LEDGER_IO_ERRORS as e:
            errors.append(str(e))
            print_error(f"Failed to normalize {p.name}: {e}")
    return written, errors, written_paths


def _finalize_reingest(
    output_dir: Path, projection_builder: object, event_store: object
) -> tuple[int, int]:
    """Link transfers and rebuild projections. Returns (modified_transfer_count, events_processed)."""
    modified = link_transfers(processed_dir=output_dir, write=True)
    events_processed = projection_builder.build_from_scratch(event_store)
    return modified, events_processed


def _display_reingest_plan(
    account: str,
    account_files: list[tuple],
    ledger_path: Path,
    purge_plan,
) -> None:
    """Print the reingest plan for the given account."""
    ledger_exists = ledger_path.exists()
    console.print(f"[bold]Reingest plan for account: {account}[/]")
    console.print(f"  Source files: {len(account_files)}")
    for p, _ in account_files:
        console.print(f"    - {p.name}")
    console.print(f"  Ledger file: {ledger_path.name} ({'exists' if ledger_exists else 'missing'})")
    console.print(f"  Events to purge: {len(purge_plan.event_ids)}")
    console.print(f"  Transactions to purge: {len(purge_plan.transaction_ids)}")


def run(
    *,
    account: str,
    workspace: Workspace,
    write: bool = False,
) -> int:
    """Purge and re-ingest all transactions for a single account."""
    config = workspace.accounts_config
    ingest_dir = workspace.ingest_dir
    output_dir = workspace.ledger_data_dir

    # Find account config
    accounts = load_accounts_config(config)
    target = None
    for acct in accounts:
        if acct.account_id == account:
            target = acct
            break

    if not target:
        print_error(f"Account '{account}' not found in config")
        return 1

    # Find source files for this account
    ingestion_service = IngestionService(accounts=accounts)
    ingestion_plan = ingestion_service.build_ingestion_plan(ingest_dir)
    account_files = [(p, aid) for p, aid in ingestion_plan.files if aid == account]

    if not account_files:
        console.print(f"[yellow]No source files matched account '{account}'[/]")
        return 1

    # Initialize event sourcing
    ready = require_event_sourcing(workspace)
    if ready is None:
        return 1
    event_store = ready.event_store
    projection_builder = ready.projection_builder

    # Plan purge
    reingest_svc = ReingestionService(
        event_store=event_store,
        projection_builder=projection_builder,
        ledger_data_dir=output_dir,
        intelligence_cache_path=workspace.intelligence_cache_path,
    )
    purge_plan = reingest_svc.build_purge_plan(account)

    ledger_path = output_dir / f"{account}.csv"
    _display_reingest_plan(account, account_files, ledger_path, purge_plan)

    if not write:
        print_dry_run_message()
        return 0

    return _execute_reingest(
        ledger_path, reingest_svc, purge_plan, account_files,
        ingestion_service, account, output_dir, event_store, projection_builder,
    )


def _execute_reingest(
    ledger_path: Path,
    reingest_svc,
    purge_plan,
    account_files: list[tuple],
    ingestion_service,
    account: str,
    output_dir: Path,
    event_store,
    projection_builder,
) -> int:
    """Delete ledger, purge events/projections, re-ingest files, rebuild projections."""
    if _delete_existing_ledger(ledger_path):
        console.print(f"[green][ok][/] Removed ledger: {ledger_path.name}")

    purge_result = reingest_svc.run_purge(purge_plan)
    console.print(f"[green][ok][/] Purged {purge_result.events_purged} events")
    console.print(f"[green][ok][/] Purged {purge_result.projections_purged} projections")
    console.print(
        f"[green][ok][/] Purged {purge_result.cache_entries_purged} cached intelligence entries"
    )

    written, _, written_paths = _reingest_source_files(
        account_files, ingestion_service, account, output_dir, event_store
    )
    for out_path in written_paths:
        console.print(f"[green][ok][/] Wrote {out_path}")

    console.print("[bold]Rebuilding projections[/]")
    modified_transfers, events_processed = _finalize_reingest(
        output_dir, projection_builder, event_store
    )
    if modified_transfers:
        console.print(
            f"[green][ok][/] Updated {modified_transfers} ledger file(s) with transfer metadata"
        )
    console.print(f"[green][ok][/] Rebuilt projections from {events_processed} events")
    console.print(f"\nDone. Re-ingested {written} file(s) for account {account}.")
    return 0
