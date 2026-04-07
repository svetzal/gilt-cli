from __future__ import annotations

"""
Reingest command — purge and re-ingest transactions for a single account.

Removes the account's ledger CSV, purges related events and projections,
clears cached intelligence, then re-runs ingestion for that account only.
"""

from gilt.ingest import load_accounts_config, normalize_file
from gilt.services.ingestion_service import IngestionService
from gilt.services.reingestion_service import ReingestionService
from gilt.transfer.linker import link_transfers
from gilt.workspace import Workspace

from .util import console, print_dry_run_message, require_event_sourcing


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

    # Load account config
    accounts = load_accounts_config(config)
    target = None
    for acct in accounts:
        if acct.account_id == account:
            target = acct
            break

    if not target:
        console.print(f"[red]Account '{account}' not found in config[/]")
        return 1

    # Find source files for this account
    ingestion_service = IngestionService(accounts=accounts)
    ingestion_plan = ingestion_service.plan_ingestion(ingest_dir)
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

    # Plan what to purge using the reingestion service
    reingest_svc = ReingestionService(
        event_store=event_store,
        projection_builder=projection_builder,
        ledger_data_dir=output_dir,
        intelligence_cache_path=workspace.intelligence_cache_path,
    )
    purge_plan = reingest_svc.plan_purge(account)

    ledger_path = output_dir / f"{account}.csv"
    ledger_exists = ledger_path.exists()

    console.print(f"[bold]Reingest plan for account: {account}[/]")
    console.print(f"  Source files: {len(account_files)}")
    for p, _ in account_files:
        console.print(f"    - {p.name}")
    console.print(f"  Ledger file: {ledger_path.name} ({'exists' if ledger_exists else 'missing'})")
    console.print(f"  Events to purge: {len(purge_plan.event_ids)}")
    console.print(f"  Transactions to purge: {len(purge_plan.transaction_ids)}")

    if not write:
        print_dry_run_message()
        return 0

    # 1. Delete ledger CSV
    if ledger_exists:
        ledger_path.unlink()
        console.print(f"[green][ok][/] Removed ledger: {ledger_path.name}")

    # 2-4. Purge events, projections, and intelligence cache via service
    purge_result = reingest_svc.execute_purge(purge_plan)
    console.print(f"[green][ok][/] Purged {purge_result.events_purged} events")
    console.print(f"[green][ok][/] Purged {purge_result.projections_purged} projections")
    console.print(
        f"[green][ok][/] Purged {purge_result.cache_entries_purged} cached intelligence entries"
    )

    # 5. Re-ingest source files
    amount_sign = ingestion_service.amount_sign_for(account)
    written = 0
    for p, acct_id in account_files:
        try:
            out_path = normalize_file(
                p,
                acct_id,
                output_dir,
                event_store=event_store,
                amount_sign=amount_sign,
            )
            console.print(f"[green][ok][/] Wrote {out_path}")
            written += 1
        except Exception as e:
            console.print(f"[red][error][/] Failed to normalize {p.name}: {e}")

    # 6. Link transfers
    modified = link_transfers(processed_dir=output_dir, write=True)
    if modified:
        console.print(f"[green][ok][/] Updated {modified} ledger file(s) with transfer metadata")

    # 7. Rebuild projections
    console.print("[bold]Rebuilding projections[/]")
    events_processed = projection_builder.rebuild_from_scratch(event_store)
    console.print(f"[green][ok][/] Rebuilt projections from {events_processed} events")

    console.print(f"\nDone. Re-ingested {written} file(s) for account {account}.")
    return 0
