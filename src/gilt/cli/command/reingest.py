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

from .. import mutations
from ..console import print_error
from ..event_sourcing_bootstrap import require_event_sourcing
from ._errors import CommandAbort
from .reingest_view import (
    display_reingest_plan,
    print_done,
    print_no_source_files,
    print_purge_results,
    print_rebuilding,
    print_rebuilt,
    print_removed_ledger,
    print_transfer_metadata,
    print_wrote,
)


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
        raise CommandAbort(1)

    # Find source files for this account
    ingestion_service = IngestionService(accounts=accounts)
    ingestion_plan = ingestion_service.build_ingestion_plan(ingest_dir)
    account_files = [(p, aid) for p, aid in ingestion_plan.files if aid == account]

    if not account_files:
        print_no_source_files(account)
        raise CommandAbort(1)

    # Initialize event sourcing
    ready = require_event_sourcing(workspace)
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

    def apply() -> int:
        return _run_reingest(
            ledger_path,
            reingest_svc,
            purge_plan,
            account_files,
            ingestion_service,
            account,
            output_dir,
            event_store,
            projection_builder,
        )

    return mutations.run_confirmed_mutation(
        matches=account_files,
        display=lambda: display_reingest_plan(account, account_files, ledger_path, purge_plan),
        confirm_prompt="",
        assume_yes=True,
        write=write,
        apply=apply,
    )


def _run_reingest(
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
        print_removed_ledger(ledger_path.name)

    purge_result = reingest_svc.run_purge(purge_plan)
    print_purge_results(purge_result)

    written, _, written_paths = _reingest_source_files(
        account_files, ingestion_service, account, output_dir, event_store
    )
    for out_path in written_paths:
        print_wrote(out_path)

    print_rebuilding()
    modified_transfers, events_processed = _finalize_reingest(
        output_dir, projection_builder, event_store
    )
    if modified_transfers:
        print_transfer_metadata(modified_transfers)
    print_rebuilt(events_processed)
    print_done(written, account)
    return 0
