from __future__ import annotations

"""
Reingest command — purge and re-ingest transactions for a single account.

Removes the account's ledger CSV, purges related events and projections,
clears cached intelligence, then re-runs ingestion for that account only.
"""

import sqlite3
from collections.abc import Sequence

from gilt.ingest import load_accounts_config, normalize_file
from gilt.model.account import Account
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.services.ingestion_service import IngestionService
from gilt.storage.event_store import EventStore
from gilt.transfer.linker import link_transfers
from gilt.workspace import Workspace

from .util import console


def _collect_transaction_ids_for_account(
    event_store: EventStore, account_id: str
) -> set[str]:
    """Find all transaction IDs imported for a given account."""
    events = event_store.get_events_by_type("TransactionImported")
    return {
        e.transaction_id
        for e in events
        if getattr(e, "source_account", None) == account_id
    }


def _collect_event_ids_to_purge(
    event_store: EventStore, account_id: str, txn_ids: set[str]
) -> set[str]:
    """Collect all event IDs that reference the account or its transactions."""
    event_ids: set[str] = set()
    all_events = event_store.get_all_events()

    for evt in all_events:
        # Events with source_account field (TransactionImported, TransactionDescriptionObserved)
        if getattr(evt, "source_account", None) == account_id:
            event_ids.add(evt.event_id)
            continue

        # Events referencing a transaction_id belonging to this account
        evt_txn_id = getattr(evt, "transaction_id", None)
        if evt_txn_id and evt_txn_id in txn_ids:
            event_ids.add(evt.event_id)
            continue

        # Duplicate events reference two transaction IDs
        for attr in ("transaction_id_1", "transaction_id_2",
                     "primary_transaction_id", "duplicate_transaction_id",
                     "original_transaction_id", "new_transaction_id"):
            ref_id = getattr(evt, attr, None)
            if ref_id and ref_id in txn_ids:
                event_ids.add(evt.event_id)
                break

    return event_ids


def _purge_events(event_store: EventStore, event_ids: set[str]) -> int:
    """Delete events from the event store by event_id."""
    if not event_ids:
        return 0
    conn = sqlite3.connect(event_store.db_path)
    try:
        placeholders = ",".join("?" for _ in event_ids)
        ids = list(event_ids)
        conn.execute(
            f"DELETE FROM event_sequence WHERE event_id IN ({placeholders})", ids
        )
        conn.execute(
            f"DELETE FROM events WHERE event_id IN ({placeholders})", ids
        )
        conn.commit()
        return len(event_ids)
    finally:
        conn.close()


def _purge_projections(workspace: Workspace, account_id: str) -> int:
    """Delete projection rows for an account."""
    proj_path = workspace.projections_path
    if not proj_path.exists():
        return 0
    conn = sqlite3.connect(proj_path)
    try:
        cursor = conn.execute(
            "DELETE FROM transaction_projections WHERE account_id = ?",
            (account_id,),
        )
        # Reset sequence metadata so incremental rebuild replays all events
        conn.execute("DELETE FROM projection_metadata")
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def _purge_intelligence_cache(workspace: Workspace, txn_ids: set[str]) -> int:
    """Remove cached intelligence entries for the account's transactions."""
    cache_path = workspace.root / "data" / "private" / "intelligence_cache.json"
    if not cache_path.exists():
        return 0

    import json

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    original_count = len(data)
    data = {k: v for k, v in data.items() if k not in txn_ids}
    removed = original_count - len(data)

    if removed > 0:
        cache_path.write_text(json.dumps(data), encoding="utf-8")

    return removed


def _amount_sign_for(account_id: str, accounts: Sequence[Account]) -> str:
    """Look up the amount_sign import hint for an account."""
    for acct in accounts:
        if acct.account_id == account_id and acct.import_hints:
            return acct.import_hints.amount_sign or "expenses_negative"
    return "expenses_negative"


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
    plan = ingestion_service.plan_ingestion(ingest_dir)
    account_files = [(p, aid) for p, aid in plan.files if aid == account]

    if not account_files:
        console.print(f"[yellow]No source files matched account '{account}'[/]")
        return 1

    # Initialize event sourcing
    es_service = EventSourcingService(workspace=workspace)
    event_store = es_service.get_event_store()

    # Collect what we'll purge
    txn_ids = _collect_transaction_ids_for_account(event_store, account)
    event_ids = _collect_event_ids_to_purge(event_store, account, txn_ids)

    ledger_path = output_dir / f"{account}.csv"
    ledger_exists = ledger_path.exists()

    console.print(f"[bold]Reingest plan for account: {account}[/]")
    console.print(f"  Source files: {len(account_files)}")
    for p, _ in account_files:
        console.print(f"    - {p.name}")
    console.print(f"  Ledger file: {ledger_path.name} ({'exists' if ledger_exists else 'missing'})")
    console.print(f"  Events to purge: {len(event_ids)}")
    console.print(f"  Transactions to purge: {len(txn_ids)}")

    if not write:
        console.print("\n[dim]Dry-run. Use --write to execute.[/]")
        return 0

    # 1. Delete ledger CSV
    if ledger_exists:
        ledger_path.unlink()
        console.print(f"[green][ok][/] Removed ledger: {ledger_path.name}")

    # 2. Purge events
    purged_events = _purge_events(event_store, event_ids)
    console.print(f"[green][ok][/] Purged {purged_events} events")

    # 3. Purge projections
    purged_projections = _purge_projections(workspace, account)
    console.print(f"[green][ok][/] Purged {purged_projections} projections")

    # 4. Purge intelligence cache
    purged_cache = _purge_intelligence_cache(workspace, txn_ids)
    console.print(f"[green][ok][/] Purged {purged_cache} cached intelligence entries")

    # 5. Re-ingest source files
    amount_sign = _amount_sign_for(account, accounts)
    written = 0
    for p, acct_id in account_files:
        try:
            out_path = normalize_file(
                p, acct_id, output_dir,
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
    projection_builder = es_service.get_projection_builder()
    events_processed = projection_builder.rebuild_from_scratch(event_store)
    console.print(f"[green][ok][/] Rebuilt projections from {events_processed} events")

    console.print(f"\nDone. Re-ingested {written} file(s) for account {account}.")
    return 0
